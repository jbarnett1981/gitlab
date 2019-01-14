#!/usr/bin/python -tt
# author: jbarnett@tableau.com
# created: 9/9/15

from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import json
import logging
import logging.handlers
import os
import re
import shutil
import subprocess

### Globals ###
# please change git_project to the name of your project name
git_project = 'puppet_nextgen'

log_file = '/var/log/puppet/gitlab-webhook.log'
# 24 MB log file size
log_max_size = 25165824
#log_level = logging.INFO
log_level = logging.DEBUG

### Logging ###
log = logging.getLogger('log')
log.setLevel(log_level)
log_handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=log_max_size, backupCount=5)
f = logging.Formatter("%(asctime)s %(filename)s %(levelname)s %(message)s", "%B %d %H:%M:%S")
log_handler.setFormatter(f)
log.addHandler(log_handler)


class webhookReceiver(BaseHTTPRequestHandler):

    def run_it(self, cmd):
        """
        runs a command
        """
        p = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log.debug('running:%s' % cmd)
        p.wait()
        if p.returncode != 0:
            log.critical("Non zero exit code:%s executing: %s" % (p.returncode, cmd))
        return p.stdout

    def run_r10k_deploy(self):
        cmd = "/usr/local/bin/r10k deploy environment -p"
        self.run_it(cmd)
        log.debug('run_r10k_deploy ends')

    def do_POST(self):
        """
        receives post, handles it
        """
        log.debug('got post')
        message = 'OK'
        self.rfile._sock.settimeout(5)
        data_string = self.rfile.read(int(self.headers['Content-Length']))
        self.send_response(200)
        self.send_header("Content-type", "text")
        self.send_header("Content-length", str(len(message)))
        self.end_headers()
        self.wfile.write(message)
        log.debug('gitlab connection should be closed now.')
        # parse data
        text = json.loads(data_string)
        repo_name = text['repository']['name']
        if repo_name == git_project:
            log.debug('project matches repo name: %s' % repo_name)
            if text['object_kind'] == 'push':
                branch = text['ref'].split('/')[2]
                try:
                    commit_author = text['commits'][0]['author']['name']
                    commit_timestamp = text['commits'][0]['timestamp']
                    commit_msg = text['commits'][0]['message'].strip('\n')
                    commit_id = text['commits'][0]['id']
                    log.debug('push event detected on branch: %s' % branch)
                    log.debug('commit author: %s' % commit_author)
                    log.debug('commit timestamp: %s' % commit_timestamp)
                    log.debug('commit message: %s' % commit_msg)
                    log.debug('commit id: %s' % commit_id)
                except IndexError:
                    log.debug('branch removal for branch: %s' % branch)
                self.run_r10k_deploy()
            if text['object_kind'] == 'merge_request':
                merge_state = text['object_attributes']['state']
                source_branch = text['object_attributes']['source_branch']
                target_branch = text['object_attributes']['target_branch']
                merge_author = text['user']['username']
                merge_timestamp = text['object_attributes']['created_at']
                merge_msg = text['object_attributes']['description']
                merge_id = text['object_attributes']['id']
                log.debug('merge request: %s' % merge_state)
                log.debug('merge_request on source branch: %s to target branch: %s' % (source_branch, target_branch))
                log.debug('merge request author/approver: %s' % merge_author)
                log.debug('merge request created on: %s' % merge_timestamp)
                log.debug('merge request message: %s' % merge_msg)
                log.debug('merge request id: %s' % merge_id)
        else:
            log.debug('project name does not match repo name. ignoring post')
        log.debug('post complete')


    def log_message(self, formate, *args):
        """
        disable printing to stdout/stderr for every post
        """
        return


def main():
    """
    the main event.
    """
    try:
        server = HTTPServer(('', 8000), webhookReceiver)
        log.info('started web server...')
        server.serve_forever()
    except KeyboardInterrupt:
        log.info('ctrl-c pressed, shutting down.')
        server.socket.close()

if __name__ == '__main__':
    main()