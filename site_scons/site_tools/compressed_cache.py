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

from abc import ABCMeta, abstractmethod
from enum import Enum, auto
from functools import partial
import gzip
import os
import pathlib
import shutil
import tempfile

import SCons


class CompressionType(Enum):
    zlib = auto()
    lz4 = auto

class CompressionError(Exception):

    def __init__(self, target, compression_name):
        self.target = target
        self.compression_name = compression_name
        self.reason = ""

    def __str__(self):
        return f"ERROR: {self.compression_name} {self.reason} for {self.target}"

class InvalidChecksum(CompressionError):
    def __init__(self, target, compression_name):
        super().__init__(target, compression_name)
        self.reason = "invalid checksum"

class DecompressFailed(CompressionError):
    def __init__(self, target, compression_name):
        super().__init__(target, compression_name)
        self.reason = "decompression failed"
class CompressFailed(CompressionError):
    def __init__(self, target, compression_name):
        super().__init__(target, compression_name)
        self.reason = "compression failed"

class UnsupportedError(Exception):

    def __init__(self, class_name, feature):
        self.class_name = class_name
        self.feature = feature

    def __str__(self):
        return f"{self.class_name} does not support {self.feature}"

class InvalidAlgorithm(Exception):

    def __init__(self, compression_type):
        self.compression_type = compression_type

    def __str__(self):
        return (f"{self.compression_type} did not map to a supported algorithm: {CompressionType.__members__.items()}")

class _CompressedCacheDir(SCons.CacheDir.CacheDir, metaclass=ABCMeta):

    @staticmethod
    @abstractmethod
    def get_ext():
        pass

    @staticmethod
    @abstractmethod
    def get_compression_name():
        pass

    @staticmethod
    @abstractmethod
    def compress(src, dst):
        pass

    @staticmethod
    @abstractmethod
    def decompress(src, dst):
        pass

    @staticmethod
    def cache_csig(dst_fobj, csig):
        size = dst_fobj.write(csig.encode())
        # We assume the size is an int that will fit into 4 bytes,
        # i.e hash itself will not be 4GB.
        dst_fobj.write((size).to_bytes(4, byteorder='big'))

    @staticmethod
    def extract_and_remove_csig(src):
        with open(src, 'rb+') as f_out:

            # Strip off 4 bytes to know the size of the hash.
            f_out.seek(-4, os.SEEK_END)
            size = int.from_bytes(f_out.read(), 'big')

            # Now use the size to extract the hash.
            f_out.seek(-size-4, os.SEEK_END)
            csig = f_out.read(size).decode()

            # Finally remove the hash from output file.
            f_out.seek(-size-4, os.SEEK_END)
            f_out.truncate()
            return csig

    @classmethod
    def copy_from_cache(cls, env, src, dst):
        if src.endswith(cls.get_ext()):
            if env.cache_timestamp_newer:
                raise UnsupportedError(cls.__name__, "timestamp-newer")
            cls.decompress(src, dst)
            csig = cls.extract_and_remove_csig(dst)
            env.File(dst).get_ninfo().csig = csig
        else:
            super().copy_from_cache(env, src, dst)

    @classmethod
    def get_cache_csig_func(cls, env, src):
        return partial(cls.cache_csig, csig=env.File(src).get_content_hash())

    @classmethod
    def copy_to_cache(cls, env, src, dst):
        cls.compress(src, dst, cls.get_cache_csig_func(env, src))

    def cachepath(self, node):
        dir, path = super().cachepath(node)
        if node.fs.exists(path):
            return dir, path
        return dir, path + self.get_ext()

    def retrieve(self, node):
        try:
            return super().retrieve(node)
        except (InvalidChecksum, DecompressFailed) as ex:
            print(ex)
            return False


    def get_cachedir_csig(self, node):
        cachedir, cachefile = self.cachepath(node)
        if cachefile and os.path.exists(cachefile):
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_hash = pathlib.Path(tmpdir) / "csig"
                cls.decompress(cachefile, tmp_hash)
                csig = cls.extract_and_remove_csig(tmp_hash)
                return csig



class CompressedCacheDir(_CompressedCacheDir):

    def __init__(self, *args, path=None, compression_type:CompressionType=None, **kwargs):
        super().__init__(*args, **kwargs)

    def __new__(cls, *args, path=None, compression_type:CompressionType=None, **kwargs):
        compression_type = kwargs.get('compression_type')
        if not compression_type:
            try:
                import lz4.frame
                return super().__new__(Lz4CacheDir)
            except ImportError:
                return super().__new__(ZlibCacheDir)
        else:
            if compression_type == CompressionType.lz4:
                import lz4.frame
                return super().__new__(Lz4CacheDir)
            elif compression_type == CompressionType.zlib:
                return super().__new__(ZlibCacheDir)
            else:
                raise InvalidAlgorithm(compression_type)

class Lz4CacheDir(CompressedCacheDir):

    @staticmethod
    def get_compression_name():
        return 'LZ4'

    @staticmethod
    def get_ext():
        return '.lz4'

    @staticmethod
    def decompress(src, dst):
        import lz4.frame
        try:
            with lz4.frame.open(src, "rb") as f_in:
                with open(dst, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

        except RuntimeError as ex:
            if "ERROR_contentChecksum_invalid" in str(ex):
                raise _CompressedCacheDir.InvalidChecksum() from ex
            else:
                raise _CompressedCacheDir.DecompressFailed() from ex

    @staticmethod
    def compress(src, dst, cache_csig_func):
        import lz4.frame

        with open(src, 'rb') as f_in:
            try:
                with lz4.frame.open(dst, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
                    cache_csig_func(f_out)
            except RuntimeError as ex:
                raise _CompressedCacheDir.CompressFailed() from ex

class ZlibCacheDir(CompressedCacheDir):

    @staticmethod
    def get_compression_name():
        return 'zlib'

    @staticmethod
    def get_ext():
        return '.gz'

    @staticmethod
    def decompress(src, dst):
        try:
            with gzip.open(src, "rb") as f_in:
                with open(dst, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        except OSError as ex:
            raise _CompressedCacheDir.DecompressFailed() from ex

    @staticmethod
    def compress(src, dst, cache_csig_func):
        try:
            with open(src, 'rb') as f_in:
                with gzip.open(dst, 'wb', compresslevel=1) as f_out:
                    shutil.copyfileobj(f_in, f_out)
                    cache_csig_func(f_out)
        except OSError as ex:
            raise _CompressedCacheDir.CompressFailed() from ex


def exists(env):
    return True

def generate(env):
    env['CACHEDIR_CLASS'] = env.get('CACHEDIR_CLASS',
        type(CompressedCacheDir(compression_type=env.get("CACHEDIR_COMPRESSION_TYPE"))))





