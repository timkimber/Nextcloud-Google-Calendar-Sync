# Nextcloud-Google-Calendar-Sync
# english
This project enables automatic synchronization of events between a Nextcloud calendar and Google Calendar. It leverages the Nextcloud API and Google Calendar API to streamline event management across both platforms. Ideal for keeping your appointments and events up to date on multiple calendars seamlessly.

In the same directory as this code, add your credentials.json file, which you retrieve from the Google Calendar API on Google Cloud:

<img width="706" alt="image" src="https://github.com/user-attachments/assets/46851e10-f1c2-484f-9f1b-31d21a950a19"> <img width="394" alt="image" src="https://github.com/user-attachments/assets/603c1f75-f391-45dd-bd85-fed490cbf3b8"> <img width="539" alt="image" src="https://github.com/user-attachments/assets/8311c1fe-440c-42de-a15d-6ed04530951d"> <img width="548" alt="image" src="https://github.com/user-attachments/assets/7d43a0b8-c8da-40fc-8c84-a4f205d32a4f"> <img width="549" alt="image" src="https://github.com/user-attachments/assets/4418453c-5971-4e24-a122-40d16486111d"> <img width="489" alt="image" src="https://github.com/user-attachments/assets/e0ec9fbc-3957-4c99-8673-445d16107763"> <img width="451" alt="image" src="https://github.com/user-attachments/assets/0462ea60-1c66-475a-9119-44e2aa503ab5">

Rename this file to credentials.json and place it in your directory.
During your first execution, it will prompt you to log in with the Google account you want to sync (this will create a token file that will reconnect automatically on each subsequent run). Log in, and your calendar will be synchronized in both directions!

(You can then set it up as a cron job on a Linux server, but that is beyond the scope of this tutorial.)
# francais
Ce projet permet de synchroniser automatiquement les événements entre un agenda Nextcloud et un compte Google Agenda. Il utilise l'API de Nextcloud et l'API de Google Calendar pour faciliter la gestion de vos événements sur les deux plateformes. Idéal pour maintenir à jour vos rendez-vous et événements sur plusieurs calendriers de manière transparente.

Dans le même répertoire que ce code, ajoutez votre fichier credentials.json, que vous récupérez via l'API Google Calendar sur Google Cloud :
<img width="706" alt="image" src="https://github.com/user-attachments/assets/46851e10-f1c2-484f-9f1b-31d21a950a19"> <img width="394" alt="image" src="https://github.com/user-attachments/assets/603c1f75-f391-45dd-bd85-fed490cbf3b8"> <img width="539" alt="image" src="https://github.com/user-attachments/assets/8311c1fe-440c-42de-a15d-6ed04530951d"> <img width="548" alt="image" src="https://github.com/user-attachments/assets/7d43a0b8-c8da-40fc-8c84-a4f205d32a4f"> <img width="549" alt="image" src="https://github.com/user-attachments/assets/4418453c-5971-4e24-a122-40d16486111d"> <img width="489" alt="image" src="https://github.com/user-attachments/assets/e0ec9fbc-3957-4c99-8673-445d16107763"> <img width="451" alt="image" src="https://github.com/user-attachments/assets/0462ea60-1c66-475a-9119-44e2aa503ab5">

Renommez ce fichier en credentials.json et placez-le dans votre répertoire.

Lors de votre première exécution, il vous sera demandé de vous connecter avec le compte Google que vous souhaitez synchroniser (cela créera ensuite un fichier token qui vous reconnectera automatiquement à chaque lancement du code). Connectez-vous, et votre agenda sera synchronisé dans les deux sens !

(Vous pouvez ensuite le paramétrer comme une tâche cron sur un serveur Linux, mais cela dépasse le cadre de ce tutoriel.)
