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
import hashlib

from SCons.Tool.MSCommon import msvc_exists, msvc_setup_env_once, msvc_version_to_maj_min

def validate_vars(env):
    """Validate the PCH and PCHSTOP construction variables."""
    if 'PCH' in env and env['PCH']:
        if 'PCHSTOP' not in env:
            raise SCons.Errors.UserError("The PCHSTOP construction must be defined if PCH is defined.")
        if not SCons.Util.is_String(env['PCHSTOP']):
            raise SCons.Errors.UserError("The PCHSTOP construction variable must be a string: %r"%env['PCHSTOP'])

def msvc_set_PCHPDBFLAGS(env):
    """
    Set appropriate PCHPDBFLAGS for the MSVC version being used.
    """
    if env.get('MSVC_VERSION',False):
        maj, min = msvc_version_to_maj_min(env['MSVC_VERSION'])
        if maj < 8:
            env['PCHPDBFLAGS'] = SCons.Util.CLVar(['${(PDB and "/Yd") or ""}'])
        else:
            env['PCHPDBFLAGS'] = ''
    else:
        # Default if we can't determine which version of MSVC we're using
        env['PCHPDBFLAGS'] = SCons.Util.CLVar(['${(PDB and "/Yd") or ""}'])


def update_scanner(env, builder):
    """Update the scanner for "builder" to also scan library dependencies."""

    old_scanner = builder.target_scanner
    if old_scanner:
        path_function = old_scanner.path_function
    else:
        path_function = None
    def new_scanner(node, env, path=()):
        if old_scanner:
            result = old_scanner.function(node, env, path)
        else:
            result = []

        pchobjs = []
        for lib in result:
            for child in lib.sources:

                if child.get_env().get('PCH'):
                    pch_obj = child.get_env().File(str(child.get_env().get('PCH'))[:-len(env['PCHSUFFIX'])] + env['PCHOBJSUFFIX'])
                    if pch_obj not in pchobjs:
                        pchobjs.append(pch_obj)

        env.AppendUnique(PCHOBJS=pchobjs)
        result += env['PCHOBJS']

        return result

    builder.target_scanner = SCons.Scanner.Scanner(
        function=new_scanner, path_function=path_function
    )

def pch_emitter(target, source, env):
    """Adds the object file target."""

    validate_vars(env)

    pch = None
    obj = None

    for t in target:
        if str(t).endswith(env['PCHSUFFIX']):
            pch = t
            env.Depends(pch, env.get('PCHCHAIN', []))
        if str(t).endswith(env['PCHOBJSUFFIX']):
            obj = t

    target = [env.File(str(pch))]

    if not obj and env.get('PCH_WINDOWS'):
        obj = str(pch)[:-len(env['PCHSUFFIX'])] + env['PCHOBJSUFFIX']
        target += [obj]

    if obj:
        env.AppendUnique(PCHOBJS=[obj])

    return (target, source)

def object_emitter(target, source, env):
    """Sets up the PCH dependencies for an object file."""

    validate_vars(env)

    if 'PCH' in env and env['PCH']:
        env.Depends(target, env['PCH'])

    return (target, source)

def get_pch_hash(path):
    m = hashlib.md5()
    m.update(path.encode('utf-8'))
    return m.hexdigest()


def includePchGenerator(target, source, env, for_signature):

    pch = env.get('PCHCHAIN', [])

    if pch:
        return ['-include-pch', pch[0]]
    return ""

def includePchChainGenerator(target, source, env, for_signature):

    if for_signature and env.get("PCHSIGNATURE"):
        return get_pch_hash(env.get("PCHSIGNATURE", ""))

    pch = env.get('PCHCHAIN', [])
    if pch:
        return ['-include-pch', pch[0]]
    return ""

def pchGccForceIncludes(target, source, env, for_signature):
    fins = env.get('FORCEINCLUDES', [])
    result = []
    no_includes = False
    if env.get("PCH_SHARED") and not str(target[0]).endswith(env.subst('$SHOBJSUFFIX')):
        no_includes = True
    chain = env.get('PCHCHAIN', [])
    first_pch = True
    for fin in fins:
        found_pch_header = False
        if chain:
            for pch in chain:
                pch_header = str(pch)[:-len(env['PCHSUFFIX'])]
                if pch_header.endswith(fin):
                    found_pch_header = True
                    break
        if not found_pch_header or (found_pch_header and first_pch and not no_includes):

            if found_pch_header:
                first_pch = False
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

                fin_header = fin
                pch_suffix = env['PCHSUFFIX']
                pch_header = str(pch)[:-len(pch_suffix)].replace('\\', '/')
                if pch_header.endswith(fin_header):
                    found = True
                    break

        if not found:
            result.append(fin)

    return result

def pchObjsGenerator(target, source, env, for_signature):
    return [obj.abspath for obj in env.get('PCHOBJS', [])]

def pchClangForceIncludes(target, source, env, for_signature):
    fins = excludePchForceIncludes(env)
    return env['_concat'](env['FORCEINCLUDEPREFIX'], fins, env['FORCEINCLUDESUFFIX'], env)

def pchSuffix(env, sources):
    if sources:
        return SCons.Util.splitext(str(sources[0]))[1] + env['PCHSUFFIX']

def pchFirstTargetGen(target, source, env, for_signature):
    return target[0]

def pchSecondTargetGen(target, source, env, for_signature):
    return target[1]

def generate(env, **kwargs):
    env['CCPCHFLAGS'] = env.get('CCPCHFLAGS', "")
    env['PCHCOMFLAGS'] = env.get('PCHCOMFLAGS', "")
    env['_INCLUDEPCH'] = ""
    env['_COMINCLUDEPCH'] = ""
    env['PCH_WINDOWS'] = False

    if sys.platform == 'win32':
        env['PCH_WINDOWS'] = True
        env['PCHSUFFIX'] = '.pch'

        env['_PCHFIRSTTARGET'] = pchFirstTargetGen
        env['_PCHSECONDTARGET'] = pchSecondTargetGen

        env['PCHCOMFLAGS'] = env['_CCCOMCOM']
        env.Append(CCPCHFLAGS=SCons.Util.CLVar(['${(PCH and "/Yu%s \\\"/Fp%s\\\""%(PCHSTOP or "",File(PCH))) or ""}']))
        env['_CCCOMCOM'] += ' $CCPCHFLAGS '
        env['_PCHOBJS'] = pchObjsGenerator


        msvc_set_PCHPDBFLAGS(env)
        compile_replace = f' /Fo$_PCHSECONDTARGET /c $SOURCES /Yl{get_pch_hash(env.get("PCHSIGNATURE", ""))} /Yc$PCHSTOP /Fp$_PCHFIRSTTARGET $PCHCOMFLAGS '
        compile_find = ' $_MSVC_OUTPUT_FLAG /c $CHANGED_SOURCES '

        from SCons.Tool.mslink import compositeLinkAction, compositeShLinkAction

        env.Append(LINKFLAGS=['$_PCHOBJS'])
        update_scanner(env, env['BUILDERS']['Program'])
        update_scanner(env, env['BUILDERS']['SharedLibrary'])

    else:

        if subprocess.getstatusoutput(f"{env['CC']} -v 2>&1 | grep -e 'LLVM version' -e 'clang version'")[0] == 0:
            env['PCHSUFFIX'] = '.pch'
            env['_FORCEINCLUDES'] = pchClangForceIncludes
            env['_INCLUDEPCH'] = includePchGenerator
            env['_COMINCLUDEPCH'] = includePchChainGenerator
            env.Append(PCHCOMFLAGS=['-Xclang', '-fno-pch-timestamp'])
        elif subprocess.getstatusoutput(f'{env["CC"]} -v 2>&1 | grep "gcc version"')[0] == 0:
            env['PCHSUFFIX'] = '.gch'
            env['_FORCEINCLUDES'] = pchGccForceIncludes

        env.Append(CCFLAGS=['-Winvalid-pch'])

        compile_replace = ' -x c++-header $PCHCOMFLAGS $_COMINCLUDEPCH '
        compile_find = ' -c '

    if env.get('PCH_SHARED'):
        copy_com = 'SHCXXCOM'
        if env['PCHSUFFIX']  != '.gch':
            env['PCHSUFFIX'] = '.dyn' + env['PCHSUFFIX']
        env['PCHCOM'] = env['SHCXXCOM'].replace(compile_find, compile_replace)
        env['PCHOBJSUFFIX'] = '.dyn' + env['SHOBJSUFFIX']
        env.Append(SHCXXFLAGS=['$_INCLUDEPCH'])
    else:
        copy_com = 'CXXCOM'
        env['PCHOBJSUFFIX'] = env['OBJSUFFIX']
        env.Append(CXXFLAGS=['$_INCLUDEPCH'])

    if compile_find in env[copy_com]:
        env['PCHCOM'] = env[copy_com].replace(compile_find, compile_replace)
    else:
        raise SCons.Error.BuildError(f"PCH builder command could not be made from {copy_com}: {env[copy_com]}\n" +
            f"Could not find '{compile_find}' string to replace in {copy_com} string.")


    if env['PCH_WINDOWS']:
        env['PCHCOM'] = env['PCHCOM'].replace('$_CCCOMCOM', '')

    pch_action = SCons.Action.Action('$PCHCOM', '$PCHCOMSTR')
    pch_builder = SCons.Builder.Builder(action=pch_action,
                                    emitter=pch_emitter,
                                    suffix=pchSuffix,
                                    source_scanner=SCons.Tool.SourceFileScanner)


    # Not supporting C precompiled headers yet
    _CSuffixes = []
    # _CSuffixes = [".c"]
    # if not SCons.Util.case_sensitive_suffixes(".c", ".C"):
    #     _CSuffixes.append(".C")

    _CXXSuffixes = [".cpp", ".cc", ".cxx", ".c++", ".C++"]
    # if SCons.Util.case_sensitive_suffixes(".c", ".C"):
    #     _CXXSuffixes.append(".C")

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

    env['BUILDERS']['PCH'] = pch_builder
    env['PCHCHAIN'] = []
    env['PCHOBJS'] = []

    env.AddMethod(excludePchForceIncludes, "ExcludePchForceIncludes")

def exists(env):
    return True
