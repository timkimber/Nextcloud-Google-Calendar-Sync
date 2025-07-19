import os
import datetime
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from caldav import DAVClient

# Scopes pour l'API Google Calendar
SCOPES = ['https://www.googleapis.com/auth/calendar']

# Chemin vers le fichier credentials pour Google API
CREDENTIALS_FILE = './credentials.json'

# Connexion à l'API Google Calendar
def connect_google_calendar():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            try:
                creds = flow.run_local_server(port=0)
            except Exception:
                # Manual authorization flow for headless environments
                flow.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'
                auth_url, _ = flow.authorization_url(prompt='consent')
                print(f'Please visit this URL to authorize the application: {auth_url}')
                auth_code = input('Enter the authorization code: ')
                flow.fetch_token(code=auth_code)
                creds = flow.credentials
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    from googleapiclient.discovery import build
    service = build('calendar', 'v3', credentials=creds)
    return service

# Connexion au calendrier Nextcloud via CalDAV
def connect_nextcloud_calendars():
    # Load Nextcloud configuration from JSON file
    try:
        with open('nextcloud_config.json', 'r') as config_file:
            config = json.load(config_file)
    except FileNotFoundError:
        print("Error: nextcloud_config.json file not found")
        raise
    except json.JSONDecodeError:
        print("Error: Invalid JSON in nextcloud_config.json")
        raise

    client = DAVClient(
        url=config['url'],
        username=config['username'],
        password=config['password']
    )
    principal = client.principal()
    calendars = principal.calendars()
    return calendars

# Récupérer les événements de Google Calendar
def get_google_events(service):
    now = datetime.datetime.utcnow()
    end_date = now + datetime.timedelta(days=30)

    time_min = now.isoformat() + 'Z'
    time_max = end_date.isoformat() + 'Z'

    events_result = service.events().list(calendarId='primary',
                                          timeMin=time_min,
                                          timeMax=time_max,
                                          singleEvents=True,
                                          orderBy='startTime').execute()
    events = events_result.get('items', [])

    google_events = []

    for event in events:
        event_summary = event.get('summary', 'No Title')

        # Vérification si l'événement est sur une journée entière ou plusieurs jours
        if 'dateTime' in event['start']:
            start = event['start']['dateTime']
            end = event['end']['dateTime']
        else:
            start = event['start']['date']
            end = event['end']['date']

        google_events.append({
            'summary': event_summary,
            'start': start,
            'end': end
        })

    return google_events

# Récupérer les événements de Nextcloud
def get_nextcloud_events(calendars):
    start = datetime.datetime.now()
    end = start + datetime.timedelta(days=30)
    all_events = []

    # Iterate through all calendars and collect events
    for calendar in calendars:
        try:
            events = calendar.date_search(start=start, end=end, expand=True)
            all_events.extend(events)
        except Exception as e:
            print(f"Error reading calendar {calendar.name}: {e}")
            continue

    return all_events

# Synchroniser les événements Google vers Nextcloud
def sync_google_to_nextcloud(google_events, nextcloud_calendars):
    # Vérifie si l'événement existe déjà dans Nextcloud
    nc_events = get_nextcloud_events(nextcloud_calendars)

    for event in google_events:
        event_summary = event['summary']
        start = event['start']
        end = event['end']

        # Convertir les dates en format datetime
        if "T" in start:
            start_dt = datetime.datetime.strptime(start[:19], "%Y-%m-%dT%H:%M:%S")
            end_dt = datetime.datetime.strptime(end[:19], "%Y-%m-%dT%H:%M:%S")
        else:
            start_dt = datetime.datetime.strptime(start, "%Y-%m-%d")
            end_dt = datetime.datetime.strptime(end, "%Y-%m-%d")

        # Vérifier si l'événement existe déjà dans Nextcloud
        event_exists = any(event_summary in nc_event.data for nc_event in nc_events)

        if not event_exists:
            # Ajouter l'événement à Nextcloud avec le bon format
            if "T" in start:
                ical_event = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Your Organization//Your Product//EN
BEGIN:VEVENT
SUMMARY:{event_summary}
DTSTART:{start_dt.strftime('%Y%m%dT%H%M%S')}
DTEND:{end_dt.strftime('%Y%m%dT%H%M%S')}
END:VEVENT
END:VCALENDAR"""
            else:
                ical_event = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Your Organization//Your Product//EN
BEGIN:VEVENT
SUMMARY:{event_summary}
DTSTART;VALUE=DATE:{start_dt.strftime('%Y%m%d')}
DTEND;VALUE=DATE:{end_dt.strftime('%Y%m%d')}
END:VEVENT
END:VCALENDAR"""

            nextcloud_calendars[0].save_event(ical_event) # Always save to the primary calendar
            print(f"Ajouté à Nextcloud: {event_summary}")

# Synchroniser les événements Nextcloud vers Google
def sync_nextcloud_to_google(service, nextcloud_calendars):

    nc_events = get_nextcloud_events(nextcloud_calendars)

    for nc_event in nc_events:
        nc_event_data = nc_event.data
        summary_line = [line for line in nc_event_data.split('\n') if line.startswith("SUMMARY:")]
        start_line = [line for line in nc_event_data.split('\n') if line.startswith("DTSTART")]
        end_line = [line for line in nc_event_data.split('\n') if line.startswith("DTEND")]

        if summary_line and start_line:
            event_summary = summary_line[0].split(":")[1]
            start = start_line[0].split(":")[1]
            # Si pas de ligne de fin, on prend le début pour événement d'une journée / If there is no end line, the start is taken as the all day event
            end = end_line[0].split(":")[1] if end_line else start

            # Gestion des événements avec ou sans heure / Event management with or without time
            if "T" in start:
                # Format avec heure / format with time
                # handle both with and without 'Z' suffix /
                if start.endswith('Z'):
                    start_dt = datetime.datetime.strptime(start, "%Y%m%dT%H%M%SZ")
                else:
                    start_dt = datetime.datetime.strptime(start, "%Y%m%dT%H%M%S")

                if "T" in end:
                    if end.endswith('Z'):
                        end_dt = datetime.datetime.strptime(end, "%Y%m%dT%H%M%SZ")
                    else:
                        end_dt = datetime.datetime.strptime(end, "%Y%m%dT%H%M%S")
                else:
                    end_dt = None
            else:
                # Format sans heure (événement d'une ou plusieurs journées entières) / Timeless format (one or more full-day event)
                start_dt = datetime.datetime.strptime(start, "%Y%m%d")
                end_dt = datetime.datetime.strptime(end, "%Y%m%d") if end else start_dt + datetime.timedelta(days=1)

            # Vérifier si l'événement existe déjà sur Google Calendar / Check if the event already exists on Google Calendar
            google_events = get_google_events(service)
            event_exists = any(event_summary in g_event['summary'] for g_event in google_events)

            if not event_exists:
                # Ajouter l'événement à Google Calendar / Add the event to Google Calendar
                if "T" in start:
                    # Format avec heure (événement précis) / Format with time (specific event)
                    event = {
                        'summary': event_summary,
                        'start': {
                            'dateTime': start_dt.isoformat() + 'Z',
                            'timeZone': 'UTC',
                        },
                        'end': {
                            'dateTime': (end_dt.isoformat() + 'Z') if end_dt else (start_dt + datetime.timedelta(hours=1)).isoformat() + 'Z',
                            'timeZone': 'UTC',
                        },
                    }
                else:
                    # Format sans heure (événement d'une ou plusieurs journées entières) / Format without time (one or more full-day event)
                    event = {
                        'summary': event_summary,
                        'start': {
                            'date': start_dt.strftime('%Y-%m-%d'),
                            'timeZone': 'UTC',
                        },
                        'end': {
                            'date': end_dt.strftime('%Y-%m-%d'),
                            'timeZone': 'UTC',
                        },
                    }

                service.events().insert(calendarId='primary', body=event).execute()
                print(f"Ajouté à Google: {event_summary}")

def main():
    # Connexion à Google Calendar
    google_service = connect_google_calendar()

    # Connexion à Nextcloud Calendar
    nextcloud_calendars = connect_nextcloud_calendars()

    # Synchroniser Google vers Nextcloud
    google_events = get_google_events(google_service)
    # Commented out until I have time to add the UID to the events and handle updates
    #sync_google_to_nextcloud(google_events, nextcloud_calendars)

    # Synchroniser Nextcloud vers Google
    sync_nextcloud_to_google(google_service, nextcloud_calendars)

if __name__ == '__main__':
    main()
