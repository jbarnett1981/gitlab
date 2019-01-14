gitlab-webhook-receiver 0.1
=====
author: Julian Barnett // jbarnett@tableau.com

The following is a script that will create a lightweight HTTP server on port 8000 and a SysV (CentOS/RedHat up to version 6.x) based init script to manage the service.

Pre-Requisites:

Python 2.7.x installed on target system and configured in the system path.

Usage:

clone this repo to a temporary location on your target system.
```
git clone git@gitlab.tableausoftware.com:devit/gitlab-webhook-receiver.git
```

copy gitlab-webhook-receiver.py to /usr/local/devit/ (create this folder if it doesn't already exist).
```
mkdir -p /usr/local/devit
cp gitlab-webhook-receiver.py /usr/local/devit/
chmod +x /usr/local/devit/gitlab-webhook-receiver.py 
```

copy the init script to init.d
```
cp gitlab-webhook-receiver /etc/init.d/
chmod +x gitlab-webhook-receiver
```

create the log file in /var/log/<your_app>/gitlab-webhook.log
```
touch /var/log/<your_app>/gitlab-webhook.log
```

add the init script to startup and start the service
```
chkconfig --add gitlab-webhook-receiver
chkconfig gitlab-webhook-receiver on
service gitlab-webhook-receiver start
```

Now you can go into your project in Gitlab and add the webhook:
Go to Settings --> Web Hooks
Add the URL of your server --> http://yourservername:8000
ensure that the trigger is 'Push Events' is checked at the very minimum. If you're dealing with branches and merging, you'll want to enable 'Merge Request Events' too.

Finally, you'll want to make sure that you have a root public RSA key created on your target server and add that as a deploy key to your project:
```
ssh-keygen -t rsa
```

Copy the contents of /root/.ssh/id_rsa.pub into a new deploy key for your project. Done!

