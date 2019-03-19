#! /usr/bin/env python

import os
import subprocess
from api_worker import APIWorker
from argparse import ArgumentParser

class NativeWorker(APIWorker):
    """API worker that executes jobs directly on the host"""
    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
        self.log_line_limit = 10
        self.cmd_prefix = kwargs['cmd_prefix']

    @staticmethod
    def lines_tail(string, tail_length):
        parts = string.split('\n')
        parts = parts[-tail_length:]
        return '\n'.join(parts)

    def launch(self, command):
        print('\n\033[1mStarting Native Job\033[0m')

        local_command = self.build_localized_command(command, self.cmd_prefix)

        stdin = None
        stdout = subprocess.PIPE
        stderr = subprocess.PIPE

        native_cmd, stdin_file, stdin_pipe, stdout_file, stdout_pipe, stderr_file, stderr_pipe = self.build_command_parts(local_command)

        native_cmd = self.cmd_prefix + native_cmd

        if stdin_file is not None:
            stdin = io.StringIO(stdin_file) if stdin_pipe else open(stdin_file, 'r')

        if stdout_file is not None:
            stdout = open(stdout_file, 'w')
        if stdout_pipe:
            assert(stdout_file is None)
            stdout_file = ''
            stdout = io.StringIO(stdout_file)

        if stderr_file is not None:
            stderr = open(stderr_file, 'w')
        if stderr_pipe:
            assert(stderr_file is None)
            stderr_file = ''
            stderr = io.StringIO(stderr_file)

        print('\nNative command:')
        print(native_cmd)
        print('stdin:  {}'.format(stdin))
        print('stdout: {}'.format(stdout))
        print('stderr: {}'.format(stderr))
        
        # Shell command used for Windows support
        process = subprocess.Popen(native_cmd, stdin=stdin, 
                                   stdout=stdout, stderr=stderr, 
                                   shell=(os.name == 'nt'))

        stdout_log, stderr_log = process.communicate()

        if stdout_log != None:
            stdout_log = self.lines_tail(stdout_log.decode(), self.log_line_limit)
        if stderr_log != None:
            stderr_log = self.lines_tail(stderr_log.decode(), self.log_line_limit)

        worker_log = 'stdout:\n{}\n\nstderr:\n{}'.format(stdout_log, stderr_log)

        stdout_data = stdout_file if stdout_pipe else None
        stderr_data = stderr_file if stderr_pipe else None

        for f in [stdin_file, stdout_file, stderr_file]:
            if f is not None:
                f.close()
        return self.worker_cleanup(command, process.returncode, worker_log, stdout_data, stderr_data)


if __name__ == '__main__': # pragma: no cover
    parser = ArgumentParser()
    parser.add_argument('cmd_prefix', nargs='+',
                        help='the command prefix of a native worker as a list of \
                              strings, takes the place of the \
                              "ENTRYPOINT" in a docker container')
    parser.add_argument('-q', '--queue', required=True, 
                        help='queue for the worker to pull work from')
    parser.add_argument('-pf', '--poll_frequency', default=1, type=int, 
                        help='time to wait between polling the work queue (seconds)')
    args = parser.parse_args()
    worker = NativeWorker(cmd_prefix=args.cmd_prefix, queue=args.queue, poll_frequency=args.poll_frequency)
    worker.run()
