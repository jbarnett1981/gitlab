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
git_project = 'Puppet'
git_master_dir = '/etc/puppet/environments/production/modules'
log_file = '/var/log/puppet/gitlab-webhook.log'
# 24 MB log file size
log_max_size = 25165824
#log_level = logging.INFO
log_level = logging.DEBUG
# external modules directory
ext_mods_dir = '/etc/puppet/external-modules'
# Production Puppetfile
puppetfile = '/etc/puppet/environments/production/Puppetfile'

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

    def git_update(self):
        """
        cleans up the master, does a pull and prune origin
        """
        log.debug('git_cleanup begins')
        os.chdir(git_master_dir)
        cmd = "git reset --hard HEAD"
        self.run_it(cmd)
        cmd = "git pull"
        self.run_it(cmd)
        cmd = "git remote prune origin"
        self.run_it(cmd)
        log.debug('git_cleanup ends')

    def install_mods(self, mods):
        """
        parses a list of module names from Puppetfile and installs them
        """
        log.debug('installing modules...')
        for mod in mods:
            cmd = "puppet module install %s --target-dir %s --version %s" % (mod.keys()[0], ext_mods_dir, mod.values()[0])
            self.run_it(cmd)
            log.debug("module (ver: %s) %s installed to %s" % (mod.values()[0], mod.keys()[0], ext_mods_dir))

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
                if branch == 'production':
                    commit_author = text['commits'][0]['author']['name']
                    commit_timestamp = text['commits'][0]['timestamp']
                    commit_msg = text['commits'][0]['message'].strip('\n')
                    commit_id = text['commits'][0]['id']
                    modified = text['commits'][0]['modified']
                    log.debug('push event detected on branch: %s' % branch)
                    log.debug('commit author: %s' % commit_author)
                    log.debug('commit timestamp: %s' % commit_timestamp)
                    log.debug('commit message: %s' % commit_msg)
                    log.debug('commit id: %s' % commit_id)
                    self.git_update()
                    if 'Puppetfile' in modified:
                        log.debug('Puppetfile updated.')
                        mods = []
                        re_pattern = '(\'([^\']+)\').+(\'(\\d.\\d.\\d)\')'
                        # If puppetfile was modified, parse through it, and attempt to install all modules
                        with open(puppetfile) as f:
                            lines = f.readlines()
                        for line in lines:
                            m = re.search(re_pattern, line)
                            try:
                                mod = {m.group(2): m.group(4)}
                                mods.append(mod)
                            except AttributeError as e:
                                pass
                        self.install_mods(mods)

                else:
                    log.debug('branch is not production (%s). ignoring post' % branch)
            elif text['object_kind'] == 'merge_request':
                merge_state = text['object_attributes']['state']
                source_branch = text['object_attributes']['source_branch']
                target_branch = text['object_attributes']['target_branch']
                if target_branch == 'production':
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
                    log.debug('target branch is not production (%s). ignoring post' % target_branch)
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