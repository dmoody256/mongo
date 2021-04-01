# Copyright 2020 MongoDB Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY
# KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#

import os
import pathlib
import shutil

import SCons

class InvalidChecksum(Exception):
    def __init__(self, target, validate_method):
        self.target = target
        self.validate_method = validate_method
        self.reason = "invalid checksum"

    def __str__(self):
        return f"ERROR: {self.validate_method} {self.reason} for {self.target}"

class UnsupportedError(Exception):

    def __init__(self, class_name, feature):
        self.class_name = class_name
        self.feature = feature

    def __str__(self):
        return f"{self.class_name} does not support {self.feature}"

class CacheDirValidate(SCons.CacheDir.CacheDir):

    @staticmethod
    def get_ext():
        return '.csig'

    @classmethod
    def copy_from_cache(cls, env, src, dst):
        if src.endswith(cls.get_ext()):
            if env.cache_timestamp_newer:
                raise UnsupportedError(cls.__name__, "timestamp-newer")

            shutil.copy2(src, dst)

            csig = None
            with open(pathlib.Path(src).parent / 'hash', 'rb') as f_out:
                csig = f_out.read().decode()

            if csig != SCons.Util.MD5filesignature(dst,
                chunksize=SCons.Node.FS.File.md5_chunksize*1024):
                raise InvalidChecksum(src, "csig md5")
        else:
            super().copy_from_cache(env, src, dst)

    @classmethod
    def copy_to_cache(cls, env, src, dst):

        # dst is bsig/file from cachepath method, so
        # we make sure to make the bsig dir first
        os.makedirs(pathlib.Path(dst).parent, exist_ok=True)
        shutil.copy2(src, dst)
        with open(pathlib.Path(dst).parent / 'hash', 'w') as f_out:
            f_out.write(env.File(src).get_content_hash())

    def retrieve(self, node):
        try:
            return super().retrieve(node)
        except (InvalidChecksum, UnsupportedError) as ex:
            print(ex)
            return False

    def get_cachedir_csig(self, node):
        cachedir, cachefile = self.cachepath(node)
        if cachefile and os.path.exists(cachefile):
            with open(pathlib.Path(cachefile).parent / 'hash', 'rb') as f_out:
                return f_out.read().decode()

    def cachepath(self, node):
        dir, path = super().cachepath(node)
        if node.fs.exists(path):
            return dir, path
        return dir, path + self.get_ext() + '/file'

def exists(env):
    return True

def generate(env):
    if not env.get('CACHEDIR_CLASS'):
        env['CACHEDIR_CLASS'] = CacheDirValidate
