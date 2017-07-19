#!/usr/bin/env python3
#
# Copyright (c) 2016-present MagicStack Inc.
# All rights reserved.
#
# See LICENSE for details.
##


import argparse
import asyncio
import os.path
import shutil
import sys
import unittest

from edgedb.server import cluster as edgedb_cluster
from edgedb.server import _testbase as tb


class TestResult:
    def wasSuccessful(self):
        return True


class TestRunner:
    def __init__(self):
        self.cases = set()

    def run(self, test):
        self.cases.update(tb.get_test_cases([test]))
        return TestResult()


async def execute(tests_dir, jobs, cluster):
    runner = TestRunner()
    unittest.main(
        module=None,
        argv=['unittest', 'discover', '-s', tests_dir],
        testRunner=runner, exit=False)

    await tb.setup_test_cases(cluster, runner.cases, jobs=jobs)


def die(msg):
    print(f'FATAL: {msg}', file=sys.stderr)
    sys.exit(1)


def parse_connect_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-D', '--data-dir', type=str,
        default=os.path.join(os.environ['HOME'], '.edgedb'),
        help='database cluster directory (default ~/.edgedb)')
    parser.add_argument(
        '-s', '--start-directory', type=str,
        help='directory to start test discovery from')
    parser.add_argument(
        '-j', '--jobs', type=int,
        help='number of parallel processes to use (defaults to CPU count)')

    args = parser.parse_args()

    if args.start_directory:
        testsdir = args.start_directory
    else:
        testsdir = os.path.abspath(os.path.dirname(__file__))

    return testsdir, args.data_dir, args.jobs


def main():
    tests_dir, data_dir, jobs = parse_connect_args()

    if os.path.exists(data_dir):
        if not os.path.isdir(data_dir):
            die(f'{data_dir!r} exists and is not a directory')
        if os.listdir(data_dir):
            die(f'{data_dir!r} exists and is not empty')

    cluster = edgedb_cluster.Cluster(data_dir)
    print(f'Bootstrapping test EdgeDB instance in {data_dir}...')

    try:
        cluster.init()
        cluster.start()
    except BaseException:
        if os.path.exists(data_dir):
            shutil.rmtree(data_dir)
        raise

    destroy_cluster = False

    loop = asyncio.get_event_loop()

    try:
        loop.run_until_complete(execute(tests_dir, jobs, cluster))
        print(f'Initialized and populated test EdgeDB instance in {data_dir}')
    except BaseException:
        destroy_cluster = True
        raise
    finally:
        cluster.stop()
        if destroy_cluster:
            cluster.destroy()
        loop.close()


if __name__ == '__main__':
    main()
