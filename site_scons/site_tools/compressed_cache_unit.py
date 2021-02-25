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

import atexit
import os
import shutil
import stat
import sys
import unittest

sys.path.append(".")
import buildscripts.scons
from site_scons.site_tools.compressed_cache import Lz4CacheDir, ZlibCacheDir
import SCons

test_env = SCons.Environment.Environment()

def generate_data(num_files, ascii_to_binary_data_ratio):
    import random
    import string
    if not os.path.exists('compression_test_data'):
        sys.stdout.write("generating test data..")
        sys.stdout.flush()
        for i in range(num_files):
            sys.stdout.write(".")
            sys.stdout.flush()
            os.makedirs('compression_test_data', exist_ok=True)
            os.makedirs('compression_test_data/outputs', exist_ok=True)
            with open("compression_test_data/" + str(i), 'wb') as f:
                for j in range(random.randint(100, 10000)):
                    if 1 == random.randint(1,int(ascii_to_binary_data_ratio)):
                        random_str = ''.join(random.choice(string.ascii_letters) for i in range(random.randint(50,400)))
                        f.write((random_str*random.randint(3,20)).encode())
                    else:
                        f.write(b"\x00"+os.urandom(random.randint(50,400))+b"\x00")
        sys.stdout.write("\n")
        sys.stdout.flush()
    return [os.path.join('compression_test_data', name) for name in os.listdir('compression_test_data') if os.path.isfile(os.path.join('compression_test_data', name))]

def make_test_case(algo, testfiles):
    class TestCompression(unittest.TestCase):

        compression_ratio = 0
        compression_size = 0
        compression_time = 0

        def md5_file(self, file):
            import hashlib
            with open(file, 'rb') as file_to_check:
                data = file_to_check.read()
                return hashlib.md5(data).hexdigest()

        def comp_ratio(self, file1, file2):
            try:
                return os.stat(file1).st_size / os.stat(file2).st_size
            except ZeroDivisionError:
                return 1

    for i, testfile in enumerate(testfiles):
        testmethodname = 'test_fn_{0}'.format(i)


        def test_compression(self):

            # Prepare some things to get ready for the test.
            decompressed = 'compression_test_data/outputs/' + os.path.basename(testfile)
            compressed = decompressed + '.lz4'
            csig = test_env.File(testfile).get_content_hash()

            # Run the test under a timer.
            from timeit import default_timer as timer
            start = timer()
            algo.compress(testfile, compressed, algo.get_cache_csig_func(test_env, testfile))
            algo.decompress(compressed, decompressed)
            csig_returned = algo.extract_and_remove_csig(decompressed)
            stop = timer()

            # Check that the test passed.
            self.assertEqual(self.md5_file(decompressed), self.md5_file(testfile))
            self.assertEqual(csig_returned, csig)

            # Sum the data for performance characterization.
            self.__class__.compression_time += (stop - start)
            self.__class__.compression_ratio += self.comp_ratio(compressed, testfile)
            self.__class__.compression_size += os.stat(testfile).st_size

            # Clean up test files generated during the test.
            os.unlink(compressed)
            os.unlink(decompressed)

        setattr(TestCompression, testmethodname, test_compression)

    def results(self):
        print(f"\n{algo.get_compression_name()} compressed/decompressed {self.compression_size/1024.0/1024.0} MBs at a rate of {(self.compression_size/1024.0/1024.0)/self.compression_time} MB/s with a ratio of {self.compression_ratio/(i+1)}")
    setattr(TestCompression, "test_results", results)

    return TestCompression

if not os.path.exists('compression_test_data'):
    testfiles = generate_data(num_files=50, ascii_to_binary_data_ratio=15)
    generated_test_data = True
else:
    testfiles = [os.path.join('compression_test_data', name) for name in os.listdir('compression_test_data') if os.path.isfile(os.path.join('compression_test_data', name))]
    generated_test_data = False

# Create a test for each file performend
for algo in [Lz4CacheDir, ZlibCacheDir]:
    klassname = algo.__name__+'_Test'
    globals()[klassname] = type(
        klassname,
        (make_test_case(algo, testfiles),),
        {})

if generated_test_data:
    def cleanup():
        shutil.rmtree('compression_test_data', ignore_errors=True)
    atexit.register(cleanup)

unittest.main()