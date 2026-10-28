# Software License Agreement (BSD License)
#
# Copyright (c) 2014, Open Source Robotics Foundation, Inc.
# Copyright (c) 2013, Willow Garage, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#  * Neither the name of Willow Garage, Inc. nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

from __future__ import print_function
from __future__ import unicode_literals

import os
import sys
import traceback

from packaging.version import parse as parse_version

# python2/3 compatibility
try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

from bloom.github import Github
from bloom.github import GithubException
from bloom.github import get_gh_info
from bloom.github import get_github_interface

from bloom.logging import debug
from bloom.logging import error
from bloom.logging import info


try:
    import rosdistro
    if parse_version(rosdistro.__version__) < parse_version('0.7.0'):
        error("rosdistro version 0.7.0 or greater is required, found '{0}' from '{1}'."
              .format(rosdistro.__version__, os.path.dirname(rosdistro.__file__)),
              exit=True)
except ImportError:
    debug(traceback.format_exc())
    error("rosdistro was not detected, please install it.", file=sys.stderr,
          exit=True)

_rosdistro_index = None
_rosdistro_distribution_files = {}
_rosdistro_index_commit = None
_rosdistro_index_original_branch = None


def get_index_url():
    global _rosdistro_index_commit, _rosdistro_index_original_branch
    index_url = rosdistro.get_index_url()
    pr = urlparse(index_url)
    if pr.netloc in ['raw.github.com', 'raw.githubusercontent.com']:
        # Try to determine what the commit hash was
        tokens = [x for x in pr.path.split('/') if x]
        if len(tokens) <= 3:
            debug("Failed to get commit for rosdistro index file: index url")
            debug(tokens)
            return index_url
        owner = tokens[0]
        repo = tokens[1]
        branch = tokens[2]
        gh = get_github_interface(quiet=True)
        if gh is None:
            # Failed to get it with auth, try without auth (may fail)
            gh = Github(username=None, auth=None)
        try:
            data = gh.get_branch(owner, repo, branch)
        except GithubException:
            debug(traceback.format_exc())
            debug("Failed to get commit for rosdistro index file: api")
            return index_url
        _rosdistro_index_commit = data.get('commit', {}).get('sha', None)
        if _rosdistro_index_commit is not None:
            info("ROS Distro index file associate with commit '{0}'"
                 .format(_rosdistro_index_commit))
            # Also mutate the index_url to use the commit (rather than the moving branch name)
            base_info = get_gh_info(index_url)
            base_branch = base_info['branch']
            rosdistro_index_commit = _rosdistro_index_commit  # Copy global into local for substitution
            middle = "{org}/{repo}".format(**base_info)
            index_url = index_url.replace("{pr.netloc}/{middle}/{base_branch}/".format(**locals()),
                                          "{pr.netloc}/{middle}/{rosdistro_index_commit}/".format(**locals()))
            info("New ROS Distro index url: '{0}'".format(index_url))
            _rosdistro_index_original_branch = base_branch
        else:
            debug("Failed to get commit for rosdistro index file: json")
    return index_url


def get_index():
    global _rosdistro_index
    if _rosdistro_index is None:
        _rosdistro_index = rosdistro.get_index(get_index_url())
        if _rosdistro_index.version == 1:
            error("This version of bloom does not support rosdistro version "
                  "'{0}', please use an older version of bloom."
                  .format(_rosdistro_index.version), exit=True)
        if _rosdistro_index.version > 4:
            error("This version of bloom does not support rosdistro version "
                  "'{0}', please update bloom.".format(_rosdistro_index.version), exit=True)
    return _rosdistro_index


def list_distributions():
    return sorted(get_index().distributions.keys())


def get_distribution_type(distro):
    return get_index().distributions[distro].get('distribution_type')


def get_python_version(distro):
    return get_index().distributions[distro].get('python_version')


def get_most_recent(thing_name, repository, reference_distro):
    reference_distro_type = get_distribution_type(reference_distro)
    distros_with_entry = {}
    get_things = {
        'release': lambda r: None if r.release_repository is None else r.release_repository,
        'doc': lambda r: None if r.doc_repository is None else r.doc_repository,
        'source': lambda r: None if r.source_repository is None else r.source_repository,
    }
    get_thing = get_things[thing_name]
    for distro in list_distributions():
        # skip distros with a different type if the information is available
        if reference_distro_type is not None:
            if get_distribution_type(distro) != reference_distro_type:
                continue
        distro_file = get_distribution_file(distro)
        if repository in distro_file.repositories:
            thing = get_thing(distro_file.repositories[repository])
            if thing is not None:
                distros_with_entry[distro] = thing
    # Choose the alphabetical last distro which contained a release of this repository
    default_distro = (sorted(distros_with_entry.keys()) or [None])[-1]
    default_thing = distros_with_entry.get(default_distro, None)
    return default_distro, default_thing


def get_distribution_file(distro):
    global _rosdistro_distribution_files
    if distro not in _rosdistro_distribution_files:
        # REP 143, get list of distribution files and take the last one
        files = rosdistro.get_distribution_files(get_index(), distro)
        if not files:
            error("No distribution files listed for distribution '{0}'."
                  .format(distro), exit=True)
        _rosdistro_distribution_files[distro] = files[-1]
    return _rosdistro_distribution_files[distro]


def get_binary_import_parents(distro, index=None):
    """Return the distributions whose binaries ``distro`` uses, nearest first.

    REP 159: a distribution that extends another with ``binary_import``
    installs into /opt/ros/<distro> and uses the parent's packages from
    /opt/ros/<parent>. ``source_rebuild`` edges are not followed: those
    packages are rebuilt into the child's own prefix. Each parent is followed
    by its own parents; with several parents the declared order is kept, and
    a duplicate keeps its first position.

    Raises RuntimeError when a declared parent cannot be read or when
    ``extends`` has a cycle.
    """
    if index is None:
        index = get_index()
    parents = []
    _collect_binary_import_parents(index, distro, _get_extends(index, distro), [distro], parents)
    return parents


def _get_extends(index, distro):
    # REP 143: the last distribution file is the one to use
    files = rosdistro.get_distribution_files(index, distro)
    if not files:
        raise RuntimeError("No distribution files listed for distribution '{0}'".format(distro))
    return getattr(files[-1], 'extends', None) or []


def _collect_binary_import_parents(index, distro, extends, chain, parents):
    for ext in extends:
        if ext['extension_method'] != 'binary_import':
            continue
        parent = ext['distro_name']
        if parent in chain:
            raise RuntimeError("Cycle in 'extends': {0}".format(' -> '.join(chain + [parent])))
        try:
            parent_index = rosdistro.get_index(ext['index_url']) if ext.get('index_url') else index
            parent_extends = _get_extends(parent_index, parent)
        except Exception as e:
            raise RuntimeError("Could not read distribution '{0}', which '{1}' extends: {2}"
                               .format(parent, distro, e))
        if parent not in parents:
            parents.append(parent)
        _collect_binary_import_parents(parent_index, parent, parent_extends, chain + [parent], parents)


def get_rosdistro_index_commit():
    return _rosdistro_index_commit


def get_rosdistro_index_original_branch():
    return _rosdistro_index_original_branch


def get_non_eol_distros_prompt():
    non_eol_distros = []
    rosdistro_index = get_index()
    for name, info in rosdistro_index.distributions.items():
        if info.get('distribution_status') != 'end-of-life':
            non_eol_distros.append(name)
    return ', '.join(non_eol_distros)


def get_binary_package_name(distro, package_name):
    """Return the platform binary package name for package_name in distro.

    If the distribution file specifies a binary_rule (REP 159), delegates to
    dist_file.get_binary_package_name(). Otherwise falls back to standard
    ros-<distro>-<pkg> naming.
    """
    try:
        dist_file = get_distribution_file(distro)
        if dist_file and hasattr(dist_file, 'get_binary_package_name'):
            return dist_file.get_binary_package_name(package_name)
    except Exception:
        pass
    return 'ros-{0}-{1}'.format(distro, package_name.replace('_', '-'))


def get_install_prefix(distro):
    """Return the installation prefix for distro.

    If the distribution file specifies an install_rule (REP 159), expands
    {distro} in install_rule. Otherwise defaults to /opt/ros/<distro>.
    """
    try:
        dist_file = get_distribution_file(distro)
        if dist_file and getattr(dist_file, 'install_rule', None):
            return dist_file.install_rule.replace('{distro}', distro)
    except Exception:
        pass
    return '/opt/ros/{0}'.format(distro)

