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

import SCons

def generate_unity_source_action(env, source, target):

    target_file = str(target[0])
    os.makedirs(os.path.dirname(target_file), exist_ok = True)
    open(target_file, 'w').close()
    with open(target_file, 'a') as f:

        for s in source:
            log_component = str(s).replace('\\', '/').replace('/', '_').replace('.', '_')
            f.write(f'#define MongoLogV2DefaultComponent_component_VAR {log_component}\n')
            f.write(f'#include "{os.path.abspath(str(s))}"\n')


def get_c_suffixes():
    # Cribbed from Tool/cc.py and Tool/c++.py. It would be better if
    # we could obtain this from SCons.
    _CSuffixes = [".c"]
    if not SCons.Util.case_sensitive_suffixes(".c", ".C"):
        _CSuffixes.append(".C")

    _CXXSuffixes = [".cpp", ".cc", ".cxx", ".c++", ".C++"]
    if SCons.Util.case_sensitive_suffixes(".c", ".C"):
        _CXXSuffixes.append(".C")

    return _CSuffixes + _CXXSuffixes

def generate_unity_source_file_name(target_node, c_source_file):
    target_path = str(target_node[0].path)
    source_path = os.path.dirname(os.path.abspath(c_source_file)).replace("\\", "/").replace("/", "_")
    ext = os.path.splitext(c_source_file)[1]
    return target_path + source_path + ext

def add_to_src_map(src_map, unity_source, c_file_source):
    if unity_source not in src_map:
        src_map[unity_source] = [c_file_source]
    else:
        if c_file_source not in src_map[unity_source]:
            src_map[unity_source] += [c_file_source]

def unity_build_emitter(target, source, env):

    if (not any("conftest" in str(t) for t in target)
        and env.get('UNITY_BUILD', True)
        and len(source) > 1):

        c_suffixes = get_c_suffixes()

        untouched_source = []
        unity_sources = []
        base_sources = set()
        src_map = dict()
        include_map = dict()
        depends_map = dict()

        for s in source:
            c_source_file = str(s.sources[0])
            c_source_ext = os.path.splitext(c_source_file)[1]

            if (c_source_ext not in c_suffixes
                or not os.path.exists(c_source_file)
                or '_gen' in c_source_file):

                untouched_source.append(s)
                continue

            s.add_ignore(s.sources)
            unity_source = generate_unity_source_file_name(target, c_source_file)

            base_sources.add(s.sources[0])
            include_map[unity_source] = c_source_file
            add_to_src_map(src_map, unity_source, c_source_file)

        for t in src_map.keys():

            unity_sources.append(env.Command(
                target=os.path.basename(t),
                source=src_map[t],
                action=SCons.Action.FunctionAction(
                    generate_unity_source_action,
                    {'strfunction':None})
                )[0])

        unity_objs = []
        if target[0].builder.get_name(env) in ['SharedLibrary', 'LoadableModule']:
            builder = env["BUILDERS"]["SharedObject"]
        else:
            builder = env["BUILDERS"]["StaticObject"]

        for s in unity_sources:
            unity_objs.append(builder(
                env=env,
                target=str(s) + builder.get_suffix(env),
                source=s,
                CPPPATH=env.get('CPPPATH', []) + [os.path.dirname(include_map[str(s.path)])],
                CCFLAGS=env.get('CCFLAGS', []) + ["-Wno-macro-redefined"],
                CPPDEFINES='UNITY_BUILDS'
            ))

        env.Depends(target, unity_objs)
        return (target, unity_objs + untouched_source)
    else:
        return (target, source)

def setup_ninja(env):

    from site_scons.site_tools.next.ninja import get_outputs, get_inputs
    def unity_build_funtion_action_conversion(env, node):

        cmd_str = f'mkdir -p {os.path.dirname(node.path)}; echo "" > {node.path}; '
        for input_node in get_inputs(node):
            log_component = input_node.replace('\\', '/').replace('/', '_').replace('.', '_')
            cmd_str += f'echo "#define MongoLogV2DefaultComponent_component_VAR {log_component}" >> {node.path}; '
            cmd_str += f'echo \'#include "{os.path.abspath(input_node)}"\' >> {node.path}; '

        return {
            'outputs': get_outputs(node),
            'inputs': get_inputs(node),
            "rule": "CMD",
            "variables": {
                "cmd": cmd_str
            },
        }
    env.NinjaRegisterFunctionHandler('generate_unity_source_action', unity_build_funtion_action_conversion)


def exists(env):
    return True

def generate(env):

    for target_builder in ['SharedLibrary', 'SharedArchive', 'LoadableModule', 'StaticLibrary', 'Program']:

        builder = env['BUILDERS'][target_builder]
        base_emitter = builder.emitter
        new_emitter = SCons.Builder.ListEmitter([base_emitter, unity_build_emitter])
        builder.emitter = new_emitter

    env.AddMethod(setup_ninja, 'NinjaUnitySetup')