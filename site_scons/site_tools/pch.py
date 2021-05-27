# Copyright 2021 MongoDB Inc.
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


import SCons
import sys
import pathlib
import subprocess


def validate_vars(env):
    """Validate the PCH and PCHSTOP construction variables."""
    if 'PCH' in env and env['PCH']:
        if 'PCHSTOP' not in env:
            raise SCons.Errors.UserError("The PCHSTOP construction must be defined if PCH is defined.")
        if not SCons.Util.is_String(env['PCHSTOP']):
            raise SCons.Errors.UserError("The PCHSTOP construction variable must be a string: %r"%env['PCHSTOP'])

def pch_emitter(target, source, env):
    """Adds the object file target."""

    validate_vars(env)

    pch = None
    obj = None

    for t in target:
        if str(t).endswith(env['PCHSUFFIX']):
            pch = t
            env.Depends(pch, env.get('PCHCHAIN', []))

    target = [pch]

    return (target, source)

def removePchExt(file):
    return SCons.Util.splitext(SCons.Util.splitext(str(file))[0])[0]

def object_emitter(target, source, env):
    """Sets up the PCH dependencies for an object file."""

    validate_vars(env)

    if 'PCH' in env and env['PCH']:
        env.Depends(target, env['PCH'])

    return (target, source)


def includePchGenerator(target, source, env, for_signature):

    pch = env.get('PCHCHAIN', [])
    if pch:
        return ['-include-pch', pch[0].abspath]

    return ""

def includePchChainGenerator(target, source, env, for_signature):

    pch = env.get('PCHCHAIN', [])
    if for_signature:
        return target[0].abspath
    if pch:
        return ['-include-pch', pch[0].abspath]

    return ""

def pchGccForceIncludes(target, source, env, for_signature):
    fins = env.get('FORCEINCLUDES', [])
    result = []

    for fin in fins:
        found = False
        chain = env.get('PCHCHAIN', [])
        if chain:
            for pch in chain[1:]:
                pch_header = str(pch)[:-len(env['PCHSUFFIX'])]
                if pch_header.endswith(fin):
                    found = True
                    break

        if not found:
            result += env['_concat'](env['FORCEINCLUDEPREFIX'], [fin], env['FORCEINCLUDESUFFIX'], env)

    return result or ""

def excludePchForceIncludes(env):
    fins = env.get('FORCEINCLUDES', [])
    result = []

    for fin in fins:

        found = False
        chain = env.get('PCHCHAIN', [])
        if chain:
            for pch in chain:
                if sys.platform == 'win32':
                    fin_header = str(pathlib.Path(str(fin)).with_suffix(''))
                    pch_suffix = '.pch'
                else:
                    fin_header = fin
                    pch_suffix = env['PCHSUFFIX']
                pch_header = str(pch)[:-len(pch_suffix)]
                if pch_header.endswith(fin_header):
                    found = True
                    break

        if not found:
            result.append(fin)

    return result

def pchClangForceIncludes(target, source, env, for_signature):
    fins = excludePchForceIncludes(env)
    return env['_concat'](env['FORCEINCLUDEPREFIX'], fins, env['FORCEINCLUDESUFFIX'], env)

def pchSuffix(env, sources):
    if sources:
        return SCons.Util.splitext(str(sources[0]))[1] + env['PCHSUFFIX']

def generate(env, **kwargs):

    if sys.platform == 'win32':
        print("ERROR: cannot not use pch tool on windows.")
        return

    if env.GetOption('link-model').startswith('dynamic'):
        shared_suf = '.dyn'
        env['PCHCOM'] = env['SHCXXCOM'].replace(' -c ', ' -x c++-header ') + ' $_COMINCLUDEPCH'
        env.Append(SHCXXFLAGS=['-Winvalid-pch', '$_INCLUDEPCH'])
    else:
        shared_suf = ''
        env['PCHCOM'] = env['CXXCOM'].replace(' -c ', ' -x c++-header ') + ' $_COMINCLUDEPCH'
        env.Append(CXXFLAGS=['-Winvalid-pch', '$_INCLUDEPCH'])
    env['PCHCOM'] = env['PCHCOM'].replace(' -o $TARGET ', ' -o ${TARGET.abspath} ')

    if subprocess.getstatusoutput(f"{env['CC']} -v 2>&1 | grep -e 'LLVM version' -e 'clang version'")[0] == 0:
        env['PCHSUFFIX'] = shared_suf + '.pch'
        env['_FORCEINCLUDES'] = pchClangForceIncludes
        env['_INCLUDEPCH'] = includePchGenerator
        env['_COMINCLUDEPCH'] = includePchChainGenerator
        env['PCHCOM'] += ' -Xclang -fno-pch-timestamp '
    elif subprocess.getstatusoutput(f'{env["CC"]} -v 2>&1 | grep "gcc version"')[0] == 0:
        env['PCHSUFFIX'] = shared_suf + '.gch'
        env['_FORCEINCLUDES'] = pchGccForceIncludes
        env['_INCLUDEPCH'] = ""
        env['_COMINCLUDEPCH'] = ""


    if 'PCHSUFFIX' not in env:
        print("ERROR: pch tool needs gcc or clang tools loaded first")
        return

    pch_action = SCons.Action.Action('$PCHCOM', '$PCHCOMSTR')
    pch_builder = SCons.Builder.Builder(action=pch_action,
                                    emitter=pch_emitter,
                                    suffix=pchSuffix,
                                    source_scanner=SCons.Tool.SourceFileScanner)


    # Cribbed from Tool/cc.py and Tool/c++.py. It would be better if
    # we could obtain this from SCons.
    _CSuffixes = [".c"]
    if not SCons.Util.case_sensitive_suffixes(".c", ".C"):
        _CSuffixes.append(".C")

    _CXXSuffixes = [".cpp", ".cc", ".cxx", ".c++", ".C++"]
    if SCons.Util.case_sensitive_suffixes(".c", ".C"):
        _CXXSuffixes.append(".C")

    suffixes = _CSuffixes + _CXXSuffixes
    for object_builder in SCons.Tool.createObjBuilders(env):
        emitterdict = object_builder.builder.emitter
        for suffix in emitterdict.keys():
            if not suffix in suffixes:
                continue
            base = emitterdict[suffix]
            emitterdict[suffix] = SCons.Builder.ListEmitter(
                [base, object_emitter]
            )

    # older ccache will not use these correctly (https://github.com/ccache/ccache/issues/235)
    # and will fail to cache the pch, but newer ccache will need these to work correctly.
    # These could be a concern for some build systems, but scons is robust
    # enough with content hashing and dependencies that its doesn't need ccache to worry.
    env['ENV']['CCACHE_SLOPPINESS'] = 'pch_defines,time_macros,include_file_ctime,include_file_mtime'


    env['BUILDERS']['PCH'] = pch_builder
    env['PCHCHAIN'] = []

def exists(env):
    env.AddMethod(excludePchForceIncludes, "ExcludePchForceIncludes")
    return sys.platform != 'win32'
