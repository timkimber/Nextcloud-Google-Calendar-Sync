import os
import datetime
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from caldav import DAVClient
from tzlocal.windows_tz import win_tz

# Scopes pour l'API Google Calendar
SCOPES = ['https://www.googleapis.com/auth/calendar']

# Chemin vers le fichier credentials pour Google API
CREDENTIALS_FILE = './credentials.json'

# Function to convert timezone names to standard format
def normalize_timezone(tz_name):
    """Convert non-standard timezone names to standard IANA timezone names"""
    if not tz_name or "/" in tz_name:
        return tz_name

    iana_tz = win_tz.get(tz_name)
    if iana_tz is None:
        return tz_name

    return iana_tz

def parse_datetime_line(line):
    """Parse a DTSTART or DTEND line to extract timezone and datetime value"""
    timezone = None

    if ";TZID=" in line:
        # Format: "DTSTART;TZID=GMT Standard Time:20250807T115500" or "DTSTART;TZID=Europe/Madrid:20250726T235500"
        parts = line.split(";TZID=")
        timezone_and_date = parts[1]
        timezone = timezone_and_date.split(":")[0]
        datetime_value = timezone_and_date.split(":", 1)[1]
    elif ";VALUE=DATE:" in line:
        # Format: "DTSTART;VALUE=DATE:20250815"
        datetime_value = line.split(";VALUE=DATE:")[1]
    else:
        # Fallback to original parsing
        datetime_value = line.split(":")[1]

    return datetime_value, timezone

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
    now = datetime.datetime.now(datetime.UTC)
    end_date = now + datetime.timedelta(days=30)

    time_min = now.isoformat()
    time_max = end_date.isoformat()

    events_result = service.events().list(calendarId='primary',
                                          timeMin=time_min,
                                          timeMax=time_max,
                                          singleEvents=True,
                                          orderBy='startTime').execute()
    events = events_result.get('items', [])
    return events

# Récupérer les événements de Nextcloud
def get_nextcloud_events(calendars):
    start = datetime.datetime.now()
    end = start + datetime.timedelta(days=30)
    all_events = []

    # Iterate through all calendars and collect events
    for calendar in calendars:
        try:
            events = calendar.search(start=start, end=end, expand=True)
            all_events.extend(events)
        except Exception as e:
            print(f"Error reading calendar {calendar.name}: {e}")
            continue

    return all_events

# Synchroniser les événements Google vers Nextcloud
def sync_google_to_nextcloud(google_events, nextcloud_calendars, nc_events):
    # Vérifie si l'événement existe déjà dans Nextcloud

    for event in google_events:
        event_summary = event.get('summary', 'No Title')

        # Vérification si l'événement est sur une journée entière ou plusieurs jours
        if 'dateTime' in event['start']:
            start = event['start']['dateTime']
            end = event['end']['dateTime']
        else:
            start = event['start']['date']
            end = event['end']['date']

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
def sync_nextcloud_to_google(service, google_events, nextcloud_calendars, nc_events):

    for nc_event in nc_events:
        nc_event_data = nc_event.data
#        print(f"Raw nextcloud event: {nc_event_data}")

        # Extract only lines between BEGIN:VEVENT and END:VEVENT
        lines = nc_event_data.split('\n')
        vevent_lines = []
        inside_vevent = False

        for line in lines:
            if line.startswith("BEGIN:VEVENT"):
                inside_vevent = True
                continue
            elif line.startswith("END:VEVENT"):
                inside_vevent = False
                break
            elif inside_vevent:
                vevent_lines.append(line)

        # Process only the VEVENT lines
        summary_line = [line for line in vevent_lines if line.startswith("SUMMARY:")]
        description_line = [line for line in vevent_lines if line.startswith("DESCRIPTION:")]
        location_line = [line for line in vevent_lines if line.startswith("LOCATION:")]
        start_line = [line for line in vevent_lines if line.startswith("DTSTART")]
        end_line = [line for line in vevent_lines if line.startswith("DTEND")]

        if summary_line and start_line:
            event_summary = summary_line[0].split(":", 1)[1]
            event_description = description_line[0].split(":", 1)[1] if description_line else ""
            event_location = location_line[0].split(":", 1)[1] if location_line else ""

            # Extract timezone information from start_line
            start_line_text = start_line[0]
            start, start_tz = parse_datetime_line(start_line_text)

            # Extract timezone information from end_line
            if end_line:
                end_line_text = end_line[0]
                end, end_tz = parse_datetime_line(end_line_text)
            else:
                # Si pas de ligne de fin, on prend le début pour événement d'une journée / If there is no end line, the start is taken as the all day event
                end = start
                end_tz = start_tz

            # Normalize timezone names to standard IANA format
            start_tz = normalize_timezone(start_tz)
            end_tz = normalize_timezone(end_tz)

            # Gestion des événements avec ou sans heure / Event management with or without time
            if "T" in start:
                # Format avec heure / format with time
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

            # Check for existing event by summary match
            existing_event = None
            for g_event in google_events:
                if event_summary == g_event.get('summary', ''):
                    existing_event = g_event
                    break

            # Prepare the Nextcloud event data for comparison
            if "T" in start:
                # Format avec heure (événement précis) / Format with time (specific event)
                nc_event_data = {
                    # 'iCalUID'
                    # 'sequence'
                    'summary': event_summary,
                    'description': event_description,
                    'location': event_location,
                    'start': {
                        'dateTime': start_dt.isoformat(),
                        'timeZone': start_tz if start_tz else 'UTC',
                    },
                    'end': {
                        'dateTime': end_dt.isoformat() if end_dt else (start_dt + datetime.timedelta(hours=1)).isoformat() + 'Z',
                        'timeZone': end_tz if end_tz else 'UTC',
                    },
                }
            else:
                # Format sans heure (événement d'une ou plusieurs journées entières) / Format without time (one or more full-day event)
                nc_event_data = {
                    'summary': event_summary,
                    'description': event_description,
                    'location': event_location,
                    'start': {
                        'date': start_dt.strftime('%Y-%m-%d'),
                    },
                    'end': {
                        'date': end_dt.strftime('%Y-%m-%d'),
                    },
                }

            if existing_event:
                # Compare fields and update if different
                needs_update = False

                # Compare summary
                if nc_event_data['summary'] != existing_event.get('summary', ''):
                    needs_update = True

                # Compare description
                if nc_event_data['description'] != existing_event.get('description', ''):
                    needs_update = True

                # Compare location
                if nc_event_data['location'] != existing_event.get('location', ''):
                    needs_update = True

                # Compare start time/date and timezone
                if 'dateTime' in nc_event_data['start']:
                    if (nc_event_data['start']['dateTime'] != existing_event.get('start', {}).get('dateTime', '') or
                        nc_event_data['start']['timeZone'] != existing_event.get('start', {}).get('timeZone', '')):
                        needs_update = True
                else:
                    if nc_event_data['start']['date'] != existing_event.get('start', {}).get('date', ''):
                        needs_update = True

                # Compare end time/date and timezone
                if 'dateTime' in nc_event_data['end']:
                    if (nc_event_data['end']['dateTime'] != existing_event.get('end', {}).get('dateTime', '') or
                        nc_event_data['end']['timeZone'] != existing_event.get('end', {}).get('timeZone', '')):
                        needs_update = True
                else:
                    if nc_event_data['end']['date'] != existing_event.get('end', {}).get('date', ''):
                        needs_update = True

                if needs_update:
                    # Update the existing Google event
#                   print("Updating Google")
                    #service.events().update(calendarId='primary', eventId=existing_event['id'], body=nc_event_data).execute()
                    if 'dateTime' in nc_event_data['start']:
#                        print(f"old: {existing_event.get('summary')} {existing_event.get('start').get('dateTime')} {existing_event.get('start').get('timeZone')} to {existing_event.get('end').get('dateTime')} {existing_event.get('end').get('timeZone')}")
                        print(f"new: {event_summary} {nc_event_data['start']['dateTime']} {nc_event_data['start']['timeZone']} to {nc_event_data['end']['dateTime']} {nc_event_data['end']['timeZone']}")
                    else:
#                       print(f"old: {existing_event.get('summary')} {existing_event.get('start').get('date')} to {existing_event.get('end').get('date')}")
                        print(f"new: {event_summary} {nc_event_data['start']['date']} to {nc_event_data['end']['date']}")
            else:
                # Create new Google event
                #service.events().insert(calendarId='primary', body=nc_event_data).execute()
                if 'dateTime' in nc_event_data['start']:
                    print(f"Ajouté à Google: {event_summary} {nc_event_data['start']['dateTime']} {nc_event_data['start']['timeZone']} to {nc_event_data['end']['dateTime']} {nc_event_data['end']['timeZone']}")
                else:
                    print(f"Ajouté à Google: {event_summary} {nc_event_data['start']['date']} to {nc_event_data['end']['date']}")

def main():
    # Connexion à Google Calendar
    google_service = connect_google_calendar()

    # Connexion à Nextcloud Calendar
    nextcloud_calendars = connect_nextcloud_calendars()

    # Get Google and Nextcloud events
    google_events = get_google_events(google_service)
    nextcloud_events = get_nextcloud_events(nextcloud_calendars)

    for i in range(min(5, len(google_events))):
        print(f"Google event {i+1}: {google_events[i]}")
        print(f"Nextcloud event {i+1}: {nextcloud_events[i].data}")
    # Synchroniser Google vers Nextcloud
    sync_google_to_nextcloud(google_events, nextcloud_calendars, nextcloud_events)

    # Synchroniser Nextcloud vers Google
    sync_nextcloud_to_google(google_service, google_events, nextcloud_calendars, nextcloud_events)

if __name__ == '__main__':
    main()
