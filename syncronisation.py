import os
import datetime
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
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    from googleapiclient.discovery import build
    service = build('calendar', 'v3', credentials=creds)
    return service

# Connexion au calendrier Nextcloud via CalDAV
def connect_nextcloud_calendar():
    client = DAVClient(
        url='https://enfantmeme.onthewifi.com/nextcloud/remote.php/dav',
        username='',#votre nom d'utilisateur d'application nextcloud
        password=''#votre mot de passe d'application nextcloud
    )
    principal = client.principal()
    calendars = principal.calendars()
    return calendars[0]  # Supposons que tu utilises le premier calendrier

# Récupérer les événements de Google Calendar
def get_google_events(service):
    now = datetime.datetime.utcnow().isoformat() + 'Z'
    events_result = service.events().list(calendarId='primary', timeMin=now,
                                          maxResults=100, singleEvents=True,
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
def get_nextcloud_events(calendar):
    start = datetime.datetime.now()
    end = start + datetime.timedelta(days=30)
    events = calendar.date_search(start=start, end=end, expand=True)
    return events

# Synchroniser les événements Google vers Nextcloud
def sync_google_to_nextcloud(google_events, nextcloud_calendar):
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

        # Vérifie si l'événement existe déjà dans Nextcloud
        nc_events = get_nextcloud_events(nextcloud_calendar)
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

            nextcloud_calendar.save_event(ical_event)
            print(f"Ajouté à Nextcloud: {event_summary}")

# Synchroniser les événements Nextcloud vers Google
def sync_nextcloud_to_google(service, nextcloud_calendar):
    nc_events = get_nextcloud_events(nextcloud_calendar)
    
    for nc_event in nc_events:
        nc_event_data = nc_event.data
        summary_line = [line for line in nc_event_data.split('\n') if line.startswith("SUMMARY:")]
        start_line = [line for line in nc_event_data.split('\n') if line.startswith("DTSTART")]
        end_line = [line for line in nc_event_data.split('\n') if line.startswith("DTEND")]
        
        if summary_line and start_line:
            event_summary = summary_line[0].split(":")[1]
            start = start_line[0].split(":")[1]
            end = end_line[0].split(":")[1] if end_line else start  # Si pas de ligne de fin, on prend le début pour événement d'une journée

            # Gestion des événements avec ou sans heure
            if "T" in start:
                # Format avec heure
                start_dt = datetime.datetime.strptime(start, "%Y%m%dT%H%M%SZ")
                end_dt = datetime.datetime.strptime(end, "%Y%m%dT%H%M%SZ") if "T" in end else None
            else:
                # Format sans heure (événement d'une ou plusieurs journées entières)
                start_dt = datetime.datetime.strptime(start, "%Y%m%d")
                end_dt = datetime.datetime.strptime(end, "%Y%m%d") if end else start_dt + datetime.timedelta(days=1)

            # Vérifier si l'événement existe déjà sur Google Calendar
            google_events = get_google_events(service)
            event_exists = any(event_summary in g_event['summary'] for g_event in google_events)
            
            if not event_exists:
                # Ajouter l'événement à Google Calendar
                if "T" in start:
                    # Format avec heure (événement précis)
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
                    # Format sans heure (événement d'une ou plusieurs journées entières)
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
    nextcloud_calendar = connect_nextcloud_calendar()

    # Synchroniser Google vers Nextcloud
    google_events = get_google_events(google_service)
    sync_google_to_nextcloud(google_events, nextcloud_calendar)

    # Synchroniser Nextcloud vers Google
    sync_nextcloud_to_google(google_service, nextcloud_calendar)

if __name__ == '__main__':
    main()
