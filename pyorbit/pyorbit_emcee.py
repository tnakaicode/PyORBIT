from __future__ import print_function
from pyorbit.classes.common import np
from pyorbit.classes.model_container_emcee import ModelContainerEmcee
from pyorbit.classes.input_parser import yaml_parser, pars_input
from pyorbit.classes.io_subroutines import pyde_save_to_pickle,\
    pyde_load_from_cpickle,\
    emcee_save_to_cpickle, emcee_load_from_cpickle, emcee_flatchain,\
    emcee_create_dummy_file, starting_point_load_from_cpickle
import pyorbit.classes.results_analysis as results_analysis
import os
import sys


__all__ = ["pyorbit_emcee_test", "yaml_parser"]


def pyorbit_emcee_test(config_in, input_datasets=None, return_output=None):

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
    reloaded_emcee_multirun = False
    reloaded_emcee = False

    try:
        mc, population, starting_point, theta_dict = pyde_load_from_cpickle(
            pyde_dir_output, prefix='')
        reloaded_pyde = True
    except:
        pass

    #first change: prob, state reloaded
    try:
        mc, starting_point, population, prob, state, sampler_chain, sampler_lnprobability, _, theta_dict = \
            emcee_load_from_cpickle(emcee_dir_output)
        reloaded_emcee = True
    except:
        pass

    try:
        starting_point, previous_boundaries, theta_dict = starting_point_load_from_cpickle(
            optimize_dir_output)
        reloaded_optimize = True
    except:
        pass

    print()
    print('reloaded_optimize: ', reloaded_pyde)
    print('reloaded_pyde: ', reloaded_pyde)
    print('reloaded_emcee: ', reloaded_emcee)
    print()

    if reloaded_pyde or reloaded_emcee:
        previous_boundaries = mc.bounds

    if reloaded_emcee:
        print('Initial Steps:', mc.emcee_parameters['nsteps'])

        if 'completed_nsteps' not in mc.emcee_parameters:
            mc.emcee_parameters['completed_nsteps'] = mc.emcee_parameters['nsteps']
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

        if mc.emcee_parameters['nsteps'] == mc.emcee_parameters['completed_nsteps']:
            
            print('Reference Time Tref: ', mc.Tref)
            print()
            print('Dimensions = ', mc.ndim)
            print('Nwalkers = ', mc.emcee_parameters['nwalkers'])
            print('Steps = ', mc.emcee_parameters['nsteps'])
            print()

            results_analysis.results_resumen(mc, flatchain)

            if return_output:
                return mc, sampler_chain, sampler_lnprobability
            else:
                return

    if not reloaded_emcee:
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

    print('emcee version: ', emcee.__version__)
    if mc.emcee_parameters['version'] == '2':
        print('WARNING: upgrading to version 3 is strongly advised')
    print()
    print('Include priors: ', mc.include_priors)
    print()
    print('Reference Time Tref: ', mc.Tref)
    print()
    print('Dimensions = ', mc.ndim)
    print('Nwalkers = ', mc.emcee_parameters['nwalkers'])
    print()
    if reloaded_emcee:
        print('Resuming from a previous run:')
        print('Performed steps = ', mc.emcee_parameters['completed_nsteps'])
        print('Final # of steps = ', mc.emcee_parameters['nsteps'])
        print()

    if not getattr(mc, 'use_threading_pool', False):
        mc.use_threading_pool = False

    print('Using threading pool:', mc.use_threading_pool)
    print()
    print('*************************************************************')
    print()

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

        print('PyDE running')
        sys.stdout.flush()

        de = DiffEvol(
            mc, mc.bounds, mc.emcee_parameters['nwalkers'], maximize=True)
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

    if mc.use_threading_pool:
        if mc.emcee_parameters['version'] == '2':
            threads_pool = emcee.interruptible_pool.InterruptiblePool(
                mc.emcee_parameters['nwalkers'])
        else:
            from multiprocessing.pool import Pool as InterruptiblePool
            threads_pool = InterruptiblePool(mc.emcee_parameters['nwalkers'])

    print()
    print('Running emcee')

    if reloaded_emcee:
        sampled = mc.emcee_parameters['completed_nsteps']
        nsteps_todo = mc.emcee_parameters['nsteps'] \
            - mc.emcee_parameters['completed_nsteps'] 
    else:
        state = None
        sampled = 0
        nsteps_todo = mc.emcee_parameters['nsteps']

    if mc.use_threading_pool:
        sampler = emcee.EnsembleSampler(
            mc.emcee_parameters['nwalkers'], mc.ndim, mc, pool=threads_pool)
    else:
        sampler = emcee.EnsembleSampler(
            mc.emcee_parameters['nwalkers'], mc.ndim, mc)

    if mc.emcee_parameters['nsave'] > 0:
        print()
        print(' Saving temporary steps')
        niter = int(nsteps_todo/mc.emcee_parameters['nsave'])

        for i in range(0, niter):
            population, prob, state = sampler.run_mcmc(
                population, mc.emcee_parameters['nsave'], 
                thin=mc.emcee_parameters['thin'], 
                rstate0=state,
                progress=True)

            sampled += mc.emcee_parameters['nsave']
            theta_dict = results_analysis.get_theta_dictionary(mc)
            emcee_save_to_cpickle(mc, starting_point, population,
                                  prob, state, sampler, theta_dict, samples=sampled)

            flatchain = emcee_flatchain(
                sampler.chain, mc.emcee_parameters['nburn'], mc.emcee_parameters['thin'])
            results_analysis.print_integrated_ACF(
                sampler.chain, theta_dict, mc.emcee_parameters['thin'])
            results_analysis.results_resumen(mc, flatchain)

            print()
            print(sampled, '  steps completed, average lnprob:, ', np.median(prob))

            sys.stdout.flush()

    else:
        population, prob, state = sampler.run_mcmc(
            population, 
            nsteps_todo, 
            thin=mc.emcee_parameters['thin'],
            rstate0=state,
            progress=True)
        
        sampled += nsteps_todo
        print(sampled)
        theta_dict = results_analysis.get_theta_dictionary(mc)
        emcee_save_to_cpickle(mc, starting_point, population,
                              prob, state, sampler, theta_dict, samples=sampled)

        flatchain = emcee_flatchain(
            sampler.chain, mc.emcee_parameters['nburn'], mc.emcee_parameters['thin'])
        results_analysis.print_integrated_ACF(
            sampler.chain, theta_dict, mc.emcee_parameters['thin'])
        results_analysis.results_resumen(mc, flatchain)
    
    print()
    print('emcee completed')

    if mc.use_threading_pool:
        # close the pool of threads
        threads_pool.close()
        threads_pool.terminate()
        threads_pool.join()

    """ A dummy file is created to let the cpulimit script to proceed with the next step"""
    emcee_create_dummy_file(mc)

    if return_output:
        return mc, sampler.chain,  sampler.lnprobability
