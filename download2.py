from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import io
import os
import pickle
import sys

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def main():

    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=1337)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token, protocol=0)
    service = build('drive', 'v3', credentials=creds)

    folder_name = ''
    folder_id = ''
    location = ''
    if len(sys.argv) > 2:
        location = sys.argv[2]
        if location[-1] != '/':
            location += '/'

    folder = service.files().list(
            q="mimeType='application/vnd.google-apps.folder'" 
            and "sharedWithMe" and "name contains '2020-12-15'",
            fields='files(id, name, parents)').execute()

    total = len(folder['files'])
    if total != 1:
        print(f'{total} folders found')
        if total == 0:
            sys.exit(1)
        prompt = 'Do you wish to download all folders listed?\n\n'
        for i in range(total):
            prompt += f'[{i}]: {get_full_path(service, folder["files"][i])}\n'
            
        prompt += '\nYour choice (0 = No) (1 = Yes): \n'
        choice = int(input(prompt))
          
        if choice==1:
            for i in range(total):    
                folder_id = folder['files'][i]['id']
                folder_name = folder['files'][i]['name']
                download_folder(service, folder_id, location, folder_name)
        else:
            sys.exit('No file has been downloaded')
    print(f'{folder_id} {folder_name}')
    download_folder(service, folder_id, location, folder_name)

def get_full_path(service, folder):

    if not 'parents' in folder:
        return folder['name']
    files = service.files().get(fileId=folder['parents'][0], fields='id, name, parents').execute()
    path = files['name'] + ' > ' + folder['name']
    while 'parents' in files:
        files = service.files().get(fileId=files['parents'][0], fields='id, name, parents').execute()
        path = files['name'] + ' > ' + path
    return path

def download_folder(service, folder_id, location, folder_name):

    if not os.path.exists(location + folder_name):
        os.makedirs(location + folder_name)
    location += folder_name + '/'

    result = []
    page_token = None
    while True:
        files = service.files().list(
                q=f"'{folder_id}' in parents",
                fields='nextPageToken, files(id, name, mimeType)',
                pageToken=page_token,
                pageSize=1000).execute()
        result.extend(files['files'])
        page_token = files.get("nextPageToken")
        if not page_token:
            break

    result = sorted(result, key=lambda k: k['name'])

    total = len(result)
    current = 1
    for item in result:
        file_id = item['id']
        filename = item['name']
        mime_type = item['mimeType']
        print(f'{file_id} {filename} {mime_type} ({current}/{total})')
        if mime_type == 'application/vnd.google-apps.folder':
            download_folder(service, file_id, location, filename)
        elif not os.path.isfile(location + filename):
            download_file(service, file_id, location, filename, mime_type)
        current += 1

def download_file(service, file_id, location, filename, mime_type):

    if 'vnd.google-apps' in mime_type:
        request = service.files().export_media(fileId=file_id,
                mimeType='application/pdf')
        filename += '.pdf'
    else:
        request = service.files().get_media(fileId=file_id)
    fh = io.FileIO(location + filename, 'wb')
    downloader = MediaIoBaseDownload(fh, request, 1024 * 1024 * 1024)
    done = False
    while done is False:
        try:
            status, done = downloader.next_chunk()
        except:
            fh.close()
            os.remove(location + filename)
            sys.exit(1)
        print(f'\rDownload {int(status.progress() * 100)}%.', end='')
        sys.stdout.flush()
    print('')

if __name__ == '__main__':
    main()
