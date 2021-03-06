from __future__ import print_function
import pyorbit
import argparse
import os
import sys

if __name__ == '__main__':

    print()
    print('PyORBIT v{0}'.format(pyorbit.__version__))
    print()
    print('Python version in use:')
    print(sys.version)
    #if sys.version_info[0] == 3 and sys.version_info[1] > 7:
    #    print('WARNING MESSAGES SUPPRESSED!')
    #print()

    parser = argparse.ArgumentParser(prog='PyORBIT_run.py', description='PyORBIT runner')
    parser.add_argument('sampler', type=str, nargs=1, help='sampler (emcee or polychord)')
    parser.add_argument('config_file', type=str, nargs=1, help='config file')

    args = parser.parse_args()
    sampler = args.sampler[0]
    file_conf = args.config_file[0]

    config_in = pyorbit.yaml_parser(file_conf)

    sampler_keyword = {
        'multinest':['multinest', 'MultiNest', 'multi'],
        'polychord':['polychord', 'PolyChord', 'polychrod', 'poly'],
        'emcee': ['emcee', 'MCMC', 'Emcee'],
        'dynesty': ['dynesty', 'DyNesty', 'Dynesty', 'DYNESTY'],
        'optimize': ['optimize', 'scipy', 'Optimize', 'OPTIMIZE'],
    }

    if sampler in sampler_keyword['emcee']:
        pyorbit.pyorbit_emcee(config_in)

    if sampler in sampler_keyword['multinest']:
        pyorbit.pyorbit_multinest(config_in)

    if sampler in sampler_keyword['polychord']:
        pyorbit.pyorbit_polychord(config_in)

    if sampler in sampler_keyword['dynesty']:
        pyorbit.pyorbit_dynesty(config_in)

    if sampler in sampler_keyword['optimize']:
        pyorbit.pyorbit_optimize(config_in)

# This line was used to check if imprtation was working
# else:
#     print 'I am being imported from another module'
