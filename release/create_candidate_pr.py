# pylint: disable=redefined-outer-name, invalid-name

"""
Creates a new release candidate branch and makes a pull request
for it into the 'release' branch.

It uses the last 'good' commit to determine what to PR,where good is defined as
the most recent commit to master that passed all the tests

"""

from __future__ import print_function

import argparse
import datetime
import logging
import sys

from release.get_token import get_token
from release.github_api import GithubApi, RequestFailed
from release import utils

logger = logging.getLogger(__name__)


def valid_date(s):
    """Convert a string into a date, for argument parsing."""
    # from: http://stackoverflow.com/a/25470943/14343
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        msg = "Not a valid date: '{0}'.".format(s)
        raise argparse.ArgumentTypeError(msg)


def _build_parser():
    """
        Constructs a command line option parser.

        Returns:
            ArgumentParser: The option parser
    """
    expected_date = utils.default_expected_release_date()

    result = argparse.ArgumentParser(
        description="""
        Create a new release candidate branch and associated pull request.
        """
    )

    result.add_argument(
        '--release-date',
        type=valid_date,
        default=expected_date,
        help="""
        Specify a date that the release branch is expected to be deployed.
        Should be in YYYY-MM-DD format. If not passed, defaults to the
        next upcoming Tuesday, which is currently {date}.
        """.format(date=expected_date.date().isoformat()),
    )
    result.add_argument(
        '--org',
        default='edx',
        help="""
        Specify a github organization to work under. Default is 'edx'.
        """
    )
    result.add_argument(
        '--repo',
        default='edx-platform',
        help="""
        Specify a github repository to work with. Default is 'edx-platform'.
        """
    )

    result.add_argument(
        '--find-commit',
        action='store_true',
        default=False,
        help="""
        Do not create a branch or a pull request. Only return the commit
        that would be used for the release candidate.
        """
    )

    return result


def create_candidate_main(raw_args):
    parser = _build_parser()
    args = parser.parse_args(raw_args)

    logger.info("Getting GitHub token...")
    token = get_token()
    github_api = GithubApi(args.org, args.repo, token)

    logger.info("Fetching commits...")
    try:
        commit = utils.most_recent_good_commit(github_api)
        commit_hash = commit['sha']
        commit_message = commit['commit']['message']
        message = utils.extract_message_summary(commit_message)
        if args.find_commit:
            logger.info(
                "\n\thash: {commit_hash}\n\tcommit message: {message}".format(
                    commit_hash=commit_hash,
                    message=message
                    )
                )
            return
    except utils.NoValidCommitsError:
        logger.error(
            "Couldn't find a recent commit without test failures. Aborting"
        )

    branch_name = utils.rc_branch_name_for_date(args.release_date.date())

    logger.info(
        "Branching {rc} off {sha}. ({msg})".format(
            rc=branch_name, sha=commit_hash, msg=message
        )
    )
    try:
        github_api.create_branch(branch_name, commit_hash)
    except RequestFailed:
        logger.error("Unable to create branch. Aborting")
        raise

    logger.info(
        "Creating Pull Request for {rc} into release".format(rc=branch_name)
    )
    try:
        request_title = "Release Candidate {rc}".format(rc=branch_name)
        github_api.create_pull_request(branch_name, title=request_title)
    except RequestFailed:
        logger.error("Unable to create branch. Aborting")
        raise

if __name__ == "__main__":
    logging.basicConfig(
        format='%(asctime)s [%(levelname)s] %(message)s',
        stream=sys.stdout
    )
    logger.setLevel(logging.INFO)
    create_candidate_main(sys.argv[1:])
