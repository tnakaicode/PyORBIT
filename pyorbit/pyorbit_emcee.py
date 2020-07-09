from __future__ import print_function
from pyorbit.classes.common import np
from pyorbit.classes.model_container_emcee import ModelContainerEmcee
from pyorbit.classes.input_parser import yaml_parser, pars_input
from pyorbit.classes.io_subroutines import pyde_save_to_pickle,\
    pyde_load_from_cpickle,\
    emcee_save_to_cpickle, emcee_load_from_cpickle, emcee_flatchain,\
    emcee_create_dummy_file, starting_point_load_from_cpickle, emcee_simpler_load_from_cpickle
import pyorbit.classes.results_analysis as results_analysis
import os
import sys
import multiprocessing

__all__ = ["pyorbit_emcee", "yaml_parser"]


def pyorbit_emcee(config_in, input_datasets=None, return_output=None):

    try:
        import emcee
    except:
        print("ERROR: emcee not installed, this will not work")
        quit()

    os.environ["OMP_NUM_THREADS"] = "1"

    optimize_dir_output = './' + config_in['output'] + '/optimize/'
    pyde_dir_output = './' + config_in['output'] + '/pyde/'

    emcee_dir_output = './' + config_in['output'] + '/emcee/'

    reloaded_optimize = False
    reloaded_pyde = False
    reloaded_emcee = False

    try:
        mc, population, starting_point, theta_dict = pyde_load_from_cpickle(
            pyde_dir_output, prefix='')
        reloaded_pyde = True
    except FileNotFoundError:
        pass

    try:
        mc, starting_point, population, prob, state, sampler_chain, \
            sampler_lnprobability, _, theta_dict, sampler = \
            emcee_load_from_cpickle(emcee_dir_output) 
        reloaded_emcee = True
    except FileNotFoundError:
        pass

    try:
        starting_point, previous_boundaries, theta_dict = starting_point_load_from_cpickle(
            optimize_dir_output)
        reloaded_optimize = True
    except FileNotFoundError:
        pass

    print()
    print('reloaded_optimize: ', reloaded_optimize)
    print('reloaded_pyde: ', reloaded_pyde)
    print('reloaded_emcee: ', reloaded_emcee)
    print()

    if reloaded_pyde or reloaded_emcee:
        previous_boundaries = mc.bounds

    if reloaded_emcee:
        print('Requested steps:', mc.emcee_parameters['nsteps'])
        
        mc.emcee_parameters['completed_nsteps'] = \
            int(sampler_chain.shape[1] * mc.emcee_parameters['thin'])
        
        print('Completed:', mc.emcee_parameters['completed_nsteps'] )
        pars_input(config_in, mc, input_datasets, reload_emcee=True)
        print('Total:', mc.emcee_parameters['nsteps'])

        """ There's no need to do anything"""
        flatchain = emcee_flatchain(
            sampler_chain, mc.emcee_parameters['nburn'], mc.emcee_parameters['thin'])
        mc.model_setup()
        mc.initialize_logchi2()

        results_analysis.print_integrated_ACF(
            sampler_chain, theta_dict, mc.emcee_parameters['thin'])

        """ In case the current startin point comes from a previous analysis """
        mc.emcee_dir_output = emcee_dir_output

        if mc.emcee_parameters['nsteps'] <= mc.emcee_parameters['completed_nsteps']:
            
            print('Reference Time Tref: ', mc.Tref)
            print()
            print('Dimensions = ', mc.ndim)
            print('Nwalkers = ', mc.emcee_parameters['nwalkers'])
            print('Steps = ', mc.emcee_parameters['nsteps'])
            print()

            results_analysis.results_resumen(mc, flatchain)
            
            print()
            print('emcee completed')
            print()

            if return_output:
                return mc, sampler_chain, sampler_lnprobability
            else:
                return

        elif not sampler:
            print('Sampler file is missing - only analysis performed with PyORBIT >8.1 cn be resumed')
            if return_output:
                return mc, sampler_chain, sampler_lnprobability
            else:
                return

    if reloaded_emcee:
        sampled = mc.emcee_parameters['completed_nsteps']
        nsteps_todo = mc.emcee_parameters['nsteps'] \
            - mc.emcee_parameters['completed_nsteps'] 

        print('Resuming from a previous run:')
        print('Performed steps = ', mc.emcee_parameters['completed_nsteps'])
        print('Final # of steps = ', mc.emcee_parameters['nsteps'])
        print('Steps to be performed = ', nsteps_todo)
        print()

    else:

        mc = ModelContainerEmcee()
        pars_input(config_in, mc, input_datasets)

        if mc.pyde_parameters['shutdown_jitter'] or mc.emcee_parameters['shutdown_jitter']:
            for dataset_name, dataset in mc.dataset_dict.items():
                dataset.shutdown_jitter()

        # keep track of which version has been used to perform emcee computations
        mc.emcee_parameters['version'] = emcee.__version__[0]

        mc.model_setup()
        mc.create_variables_bounds()
        mc.initialize_logchi2()

        results_analysis.results_resumen(mc, None, skip_theta=True)

        mc.pyde_dir_output = pyde_dir_output
        mc.emcee_dir_output = emcee_dir_output

        mc.emcee_parameters['nwalkers'] = mc.ndim * \
            mc.emcee_parameters['npop_mult']
        if mc.emcee_parameters['nwalkers'] % 2 == 1:
            mc.emcee_parameters['nwalkers'] += 1

        if not os.path.exists(mc.emcee_dir_output):
            os.makedirs(mc.emcee_dir_output)

        state = None
        sampled = 0
        nsteps_todo = mc.emcee_parameters['nsteps']

    print('Include priors: ', mc.include_priors)
    print()
    print('Reference Time Tref: ', mc.Tref)
    print()
    print('Dimensions = ', mc.ndim)
    print('Nwalkers = ', mc.emcee_parameters['nwalkers'])
    print()

    if mc.emcee_parameters['version'] == '2':
        mc.emcee_parameters['use_threading_pool'] = False

    if not mc.pyde_parameters.get('use_threading_pool', False):
        mc.pyde_parameters['use_threading_pool'] = False

    if not mc.emcee_parameters.get('use_threading_pool', False):
        mc.emcee_parameters['use_threading_pool'] = False


    if reloaded_emcee:
        sys.stdout.flush()
        pass
    elif reloaded_pyde:

        theta_dict_legacy = theta_dict.copy()
        population_legacy = population.copy()

        theta_dict = results_analysis.get_theta_dictionary(mc)
        population = np.zeros(
            [mc.emcee_parameters['nwalkers'], mc.ndim], dtype=np.double)

        for theta_name, theta_i in theta_dict.items():
            population[:, theta_i] = population_legacy[:,
                                                       theta_dict_legacy[theta_name]]
            mc.bounds[theta_i] = previous_boundaries[theta_dict_legacy[theta_name]]

        starting_point = np.median(population, axis=0)
        # print(starting_point)
        # print(population)

        print('Using previous population as starting point. ')
        print()
        sys.stdout.flush()

    elif mc.starting_point_flag or reloaded_optimize:

        if reloaded_optimize:
            print('Using the output from a previous optimize run as starting point')
            theta_dict_legacy = theta_dict.copy()
            starting_point_legacy = starting_point.copy()
            theta_dict = results_analysis.get_theta_dictionary(mc)
            for theta_name, theta_i in theta_dict.items():
                starting_point[theta_i] = starting_point_legacy[theta_dict_legacy[theta_name]]
        else:
            print('Using user-defined starting point from YAML file')
            mc.create_starting_point()
            starting_point = mc.starting_point

        population = np.zeros(
            [mc.emcee_parameters['nwalkers'], mc.ndim], dtype=np.double)
        for ii in range(0, mc.emcee_parameters['nwalkers']):
            population[ii, :] = np.random.normal(starting_point, 0.0000001)

        print(
            'to create a synthetic population extremely close to the starting values.')
        print()

        sys.stdout.flush()

    else:
        """ None of the previous cases has been satisfied, we have to run PyDE """
        try:
            from pyde.de import DiffEvol
        except ImportError:
            print('ERROR! PyDE is not installed, run first with optimize instead of emcee')
            quit()

        if not os.path.exists(mc.pyde_dir_output):
            os.makedirs(mc.pyde_dir_output)

        print('Using threading pool for PyDE:', 
            mc.pyde_parameters['use_threading_pool'])

        print('PyDE running')
        sys.stdout.flush()

        if mc.pyde_parameters['use_threading_pool']:
            with multiprocessing.Pool() as pool:

                de = DiffEvol(
                    mc,
                    mc.bounds,
                    mc.emcee_parameters['nwalkers'], 
                    maximize=True,
                    pool=pool)

                de.optimize(int(mc.pyde_parameters['ngen']))
        else:
            de = DiffEvol(
                mc,
                mc.bounds,
                mc.emcee_parameters['nwalkers'], 
                maximize=True)

            de.optimize(int(mc.pyde_parameters['ngen']))            

        population = de.population
        starting_point = np.median(population, axis=0)

        theta_dict = results_analysis.get_theta_dictionary(mc)

        """ bounds redefinition and fix for PyDE anomalous results """
        if mc.recenter_bounds_flag:
            pyde_save_to_pickle(
                mc, population, starting_point, theta_dict, prefix='orig')

            mc.recenter_bounds(starting_point)
            population = mc.fix_population(starting_point, population)
            starting_point = np.median(population, axis=0)

            print('Boundaries redefined after PyDE output')

        pyde_save_to_pickle(mc, population, starting_point, theta_dict)

        print('PyDE completed')
        print()
        sys.stdout.flush()

    if not reloaded_emcee:
        results_analysis.results_resumen(
            mc, starting_point, compute_lnprob=True, is_starting_point=True)
        sys.stdout.flush()

    print()
    print('*************************************************************')
    print()
    print('Running emcee')
    print()
    print('emcee version: ', emcee.__version__)
    if mc.emcee_parameters['version'] == '2':
        print('WARNING: upgrading to version 3 is strongly advised')
    print('Using threading pool for emcee:', mc.emcee_parameters.get('use_threading_pool', False))
    print()

    if reloaded_emcee:
        print('Using reloaded sampler')
        print()
    else:
        sampler = emcee.EnsembleSampler(
            mc.emcee_parameters['nwalkers'], mc.ndim, mc)

    if mc.emcee_parameters['nsave'] > 0:
        print('Saving temporary steps')
        print()
        niter = int(np.ceil(nsteps_todo/mc.emcee_parameters['nsave']))

        for i in range(0, niter):

            if mc.emcee_parameters['use_threading_pool']:
                with multiprocessing.Pool() as pool:
                    sampler.pool = pool
                    population, prob, state = sampler.run_mcmc(
                        population,
                        mc.emcee_parameters['nsave'],
                        thin=mc.emcee_parameters['thin'],
                        rstate0=state,
                        progress=True)
            else:
                population, prob, state = sampler.run_mcmc(
                    population,
                    mc.emcee_parameters['nsave'],
                    thin=mc.emcee_parameters['thin'],
                    rstate0=state,
                    progress=True)

            sampled += mc.emcee_parameters['nsave']
            theta_dict = results_analysis.get_theta_dictionary(mc)
            emcee_save_to_cpickle(mc, starting_point, population,
                                  prob, state, sampler, theta_dict, 
                                  samples=sampled)

            flatchain = emcee_flatchain(
                sampler.chain,
                mc.emcee_parameters['nburn'],
                mc.emcee_parameters['thin'])

            results_analysis.print_integrated_ACF(
                sampler.chain,
                theta_dict,
                mc.emcee_parameters['thin'])

            results_analysis.results_resumen(mc, flatchain)

            print()
            print(sampled, '  steps completed, average lnprob:, ', np.median(prob))
            print()
            sys.stdout.flush()

            # It turns out that reloading the sampler from the file will
            # result in faster parallelization...
            state, sampler = emcee_simpler_load_from_cpickle(emcee_dir_output)

    else:
        if mc.emcee_parameters['use_threading_pool']:
            with multiprocessing.Pool() as pool:
                sampler.pool = pool
                population, prob, state = sampler.run_mcmc(
                    population,
                    nsteps_todo,
                    thin=mc.emcee_parameters['thin'],
                    rstate0=state,
                    progress=True)

        else:
            population, prob, state = sampler.run_mcmc(
                population,
                nsteps_todo,
                thin=mc.emcee_parameters['thin'],
                rstate0=state,
                progress=True)

        sampled += nsteps_todo

        theta_dict = results_analysis.get_theta_dictionary(mc)
        emcee_save_to_cpickle(mc, starting_point, population,
                              prob, state, sampler, theta_dict, 
                              samples=sampled)

        flatchain = emcee_flatchain(
            sampler.chain,
            mc.emcee_parameters['nburn'],
            mc.emcee_parameters['thin'])

        results_analysis.print_integrated_ACF(
            sampler.chain,
            theta_dict,
            mc.emcee_parameters['thin'])

        results_analysis.results_resumen(mc, flatchain)

    print()
    print('emcee completed')
    print()

    """ A dummy file is created to let the cpulimit script to proceed with the next step"""
    emcee_create_dummy_file(mc)

    if return_output:
        return mc, sampler.chain,  sampler.lnprobability
