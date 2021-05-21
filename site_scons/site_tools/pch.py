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
        if SCons.Util.splitext(str(t))[1] == env['PCHSUFFIX']:
            pch = t
            env.Depends(pch, env.get('PCHCHAIN', []))

    target = [pch]

    return (target, source)

def removePchExt(file):
    return SCons.Util.splitext(SCons.Util.splitext(str(file))[0])[0]

def object_emitter(target, source, env, parent_emitter):
    """Sets up the PCH dependencies for an object file."""

    validate_vars(env)

    parent_emitter(target, source, env)

    if 'PCH' in env and env['PCH']:
        env.Depends(target, env['PCH'])

    return (target, source)

def static_object_emitter(target, source, env):
    return object_emitter(target, source, env,
                          SCons.Defaults.StaticObjectEmitter)

def shared_object_emitter(target, source, env):
    return object_emitter(target, source, env,
                          SCons.Defaults.SharedObjectEmitter)

CSuffixes = ['.c', '.C']
CXXSuffixes = ['.cc', '.cpp', '.cxx', '.c++', '.C++']

def includePchGenerator(target, source, env, for_signature):
    pch = env.get('PCH')
    if pch:
        return ['-include-pch', pch]
    return ""



def pchGccForceIncludes(target, source, env, for_signature):
    fins = env.get('FORCEINCLUDES', [])
    result = []

    for fin in fins:
        found = False
        chain = env.get('PCHCHAIN', [])
        if chain:
            for pch in chain[1:]:
                pch_header = str(pathlib.Path(str(pch)).with_suffix(''))
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
                else:
                    fin_header = fin
                pch_header = str(pathlib.Path(str(pch)).with_suffix(''))
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

    if subprocess.getstatusoutput(f"{env['CC']} -v 2>&1 | grep -e 'LLVM version' -e 'clang version'")[0] == 0:
        env['PCHSUFFIX'] = '.pch'
        env['_FORCEINCLUDES'] = pchClangForceIncludes
        env['_INCLUDEPCH'] = includePchGenerator
    elif subprocess.getstatusoutput(f'{env["CC"]} -v 2>&1 | grep "gcc version"')[0] == 0:
        env['PCHSUFFIX'] = '.gch'
        env['_FORCEINCLUDES'] = pchGccForceIncludes
        env['_INCLUDEPCH'] = ""

    if 'PCHSUFFIX' not in env:
        print("ERROR: pch tool needs gcc or clang tools loaded first")
        return

    pch_action = SCons.Action.Action('$PCHCOM', '$PCHCOMSTR')
    pch_builder = SCons.Builder.Builder(action=pch_action,
                                    emitter=pch_emitter,
                                    suffix=pchSuffix,
                                    source_scanner=SCons.Tool.SourceFileScanner)

    static_obj, shared_obj = SCons.Tool.createObjBuilders(env)
    for suffix in CSuffixes:
        static_obj.add_emitter(suffix, static_object_emitter)
        shared_obj.add_emitter(suffix, shared_object_emitter)

    for suffix in CXXSuffixes:
        static_obj.add_emitter(suffix, static_object_emitter)
        shared_obj.add_emitter(suffix, shared_object_emitter)

    env['PCHCOM'] = env['CXXCOM'].replace(' -c ', ' -x c++-header ') + ' $_INCLUDEPCH'
    env.Append(CCFLAGS=['-Winvalid-pch', '$_INCLUDEPCH'])
    env['BUILDERS']['PCH'] = pch_builder
    env['PCHCHAIN'] = []

def exists(env):
    env.AddMethod(excludePchForceIncludes, "ExcludePchForceIncludes")
    return sys.platform != 'win32'
