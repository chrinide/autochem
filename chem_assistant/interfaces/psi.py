#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
File: psi.py 
Author: Tom Mason
Email: tommason14@gmail.com
Github: https:github.com/tommason14
Description: Interface between Python and PSI4 input files 
"""

from ..core.atom import Atom
from ..core.molecule import Molecule
from ..core.settings import (Settings, read_template, dict_to_settings)
from ..core.job import Job
from ..core.periodic_table import PeriodicTable as PT
from ..core.sc import Supercomp
from ..core.utils import search_dict_recursively

from os import (chdir, mkdir, getcwd, system)
from os.path import (exists, join, dirname)

__all__ = ['PsiJob']

class PsiJob(Job):
    # Note the job scripts require the supercomputer to be entered, such as:

    # >>> j = PsiJob(using = 'file.xyz')
    # >>> j.supercomp = 'raijin'
    """Class for creating PSI4 input files and job scripts. 
    
    The input files generated default to single point energy calculations using MP2/cc-pVTZ, with frozen core orbitals- for this reason, these single point calculations are very fast. This is easily changed by creating a |Settings| object and adding parameters, using the following syntax.

    >>> s = Settings()
    >>> s.input.globals.basis= 'cc-pVDZ'
    >>> s.input.molecule.extra_value = 'extra'
    >>> j = PsiJob(using = '../xyz_files/mesylate.xyz', settings = s)

    This yields the following result:

        memory 32 Gb

        molecule complex {
        -1 1
         C      -11.52615475      2.13587901     -3.92614475
         H      -12.17727298      1.37283268     -4.39314733
         H      -12.13111156      2.84527650     -3.33020803
         H      -10.95289836      2.67720525     -4.70258006
         S      -10.36648767      1.31567304     -2.82897636
         O       -9.54405868      2.38757303     -2.22205822
         O      -11.24567273      0.60890457     -1.83183396
         O       -9.60100212      0.36690604     -3.68579623
        units angstrom
        no_reorient
        symmetry c1
        extra_value extra
        }

        set globals {
            basis cc-pVDZ
            scf_type DF
            freeze_core True
            guess sad
            S_ORTHOGONALIZATION canonical
        }

        energy('mp2')

    Options are added in sections: 
        - self.input.molecule for any key value pair in the molecule section
        - self.input.unbound for any key value pair outside of molecule and globals. The value can be a string or a list.
            >>> self.input.unbound.key = 'value'
            # key value
             >>> self.input.unbound.key2 = 'value value value'
            # key value value value
            >>> self.input.unbound.key = ['value1', 'value2', 'value3']
            # key value1 value2 value3
        - self.input.globals for the 'set globals' section
        - any options not enclosed in braces appear before the last line
        - To change the run type:
            >>> self.input.run = {'optimize': 'scf'}
            # optimize('scf')
        - If extra run options are required:
            >>> self.input.run.additional = {'dertype': 'energy'} 
            # optimize('scf', dertype='energy')
            >>> self.input.run.additional = {'dertype': 'energy', 'option2': 'value'} 
            # optimize('scf', dertype='energy', 'option2'='value')
        NOTE: An option for adding commands outside of the molecule and globals section needs to be added.                        
    
    The names of files created default to the type of calculation: optimisation (opt), single point
energy (spec) or hessian matrix calculation for thermochemical data and vibrational frequencies (hess). If a different name is desired, pass a string with the ``filename`` parameter, with no extension. The name will be used for both input and job files.
        >>> job = GamessJob(using = 'file.xyz', filename = 'benzene')
    This command produces two files, benzene.inp and benzene.job.
    
    If a system is comprised of multiple fragments, each fragment can have its own input file created in a subdirectory by passing in ``frags_in_subdir`` = True.

    Files are placed in a subdirectory of their own name. So when creating optimisation files, files are placed in opt:
        .
        └── opt
            ├── opt.inp
            └── opt.job
    """
    def __init__(self, using = None, frags_in_subdir = False, settings = None, filename = None, is_complex = False, **kwargs):
        super().__init__(using)
        self.filename = filename
        self.defaults = read_template('psi.json') #settings object 
        if settings is not None:
            # can only have one run type, currently- need to delete the energy if running an
            # optimisation, for example
            if 'run' in settings.input.keys():
                del self.defaults.input.run
            self.fetch_info(settings)
        else:
            self.input = self.defaults.input
        super().title()
        
        self.is_complex = is_complex # creates a `complex` dir

        super().output_data(PsiJob, 'molecule.charge', 'molecule.multiplicity', frags_in_subdir)

    def fetch_info(self, settings):
        self.merged = self.defaults.merge(settings) # merges inp, job data 
        self.input = self.merged.input
        self.job = self.merged.job
        
    def make_header(self):
        """Transform all contents of |Settings| objects into PSI4 input file headers, containing all the information pertinent to the calculation"""
        comment = f"# PSI4 Calc: {self.title}\n\n"
        mem  = f"memory {self.input.memory}\n\n"
        mol = "molecule complex {\n"
        charge = f"{self.input.molecule.charge} {self.input.molecule.multiplicity}\n"
        atoms = ""
        for atom in self.mol.coords:
            atoms += f" {atom.symbol:5s} {atom.x:>10.5f} {atom.y:>10.5f} {atom.z:>10.5f}\n"
        units = f"units {self.input.molecule.units}\n"
        sym = f"symmetry {self.input.molecule.symmetry}\n"
        reorient = "no_reorient\n"
        end = "}\n"
                
        data = [comment, mem, mol, charge, atoms, units, reorient, sym,  end]
        
        # add in user options
        for key, value in self.input.molecule.items():
            if key not in ("charge", "multiplicity", "units", "symmetry"):
                key = f"{key} {value}\n"
                data.insert(-1, key) #insert before last item
        self.inp = data

    def add_unbound(self):
        """May never be required- but this adds options between the molecule and global sections.
        Returns a dictionary of terms- might need more than two terms on same line = nested dict """

        vals = search_dict_recursively(self.input.unbound)
        if vals != {}: # if not empty
            self.inp.append('\n')
            for key, value in vals.items():
                if isinstance(value, list):
                    self.inp.append(f"{key} {' '.join(value)}\n")
                elif isinstance(value, str):
                    self.inp.append(f"{key} {value}\n")

    def add_globals(self):
        self.inp.append('\nset globals {\n')
        for key, value in self.input.globals.items():
            self.inp.append(f"    {key} {value}\n")
        self.inp.append('}\n')

    def add_run(self):
        res = []
        # list of tuples- to ensure the 'normal' entry, the one defined input.run, appears first
        # in the list by adding a counter. In testing, {optimize: scf} with additional {dertype:
        # energy} produced dertype('energy', optimize='scf'), not optimize('scf', dertype='energy')
        # due to alphabetical ordering of [('dertype', 'energy'), ('optimize', 'scf')]
        # probably should have just made two lists of tuples, one for normal, one for additional
        for k,v in self.input.run.items():
            if k != 'additional':
                res.append((0, k, v))
            if k == 'additional': 
                counter = 1
                for k1, v1 in self.input.run[k].items():
                    res.append((counter, k1, v1)) 
                    counter += 1
                # if I ever need to add two different types of run in the same file,
                # comment out the two lines above, add in the 3 below, and add an additional
                # dict key: (AND CHANGE DOCSTRING)
                # would need to add resulting string to a list and then concatenate that list with
                # self.inp as well, otherwise you would have a combination in the same line
                ##############
                # s = Settings()
                # s.input.run = {'optimize': 'scf'}
                # s.input.run.additional = {'optimize' :{'dertype': 'energy',
                #                                        'entry': 'value'}}
                ##############
                # for data in self.input.run[k].values():
                #     for k1, v1 in data.items():
                #         res.append((k1, v1))
        res = sorted(res, key = lambda val: val[0]) #sort by the first item of tuple, the number
        string = f"{res[0][1]}('{res[0][2]}'"
        for val in res[1:]:
            string += f", {val[1]}='{val[2]}'"
        string += ')'
        self.inp.append(string)
        self.inp = "".join(self.inp)
 
    def file_basename(self):
        """If no filename is passed when the class is instantiated, the name of the file defaults to
        the run type: a geometry optimisation (opt), single point energy calculation (spec), or a hessian matrix calculation for vibrational frequencies (hess). This method creates an attribute ``base_name``, used in creating the input and job files."""
        for key in self.input.run.keys(): #run, or additional
            if key != 'additional':
                nom = key
        if self.filename == None:
            options = {'optimize': 'opt', 'energy': 'spec', 'frequency': 'hess'}
            self.base_name = options.get(nom, 'file') #default name = file
        else:
            self.base_name = self.filename

    def create_inp(self):
        self.make_header()
        self.add_unbound()
        self.add_globals()
        self.add_run()
        self.file_basename()
        super().write_file(self.inp, filetype = 'inp')

    def change_mgs_job(self, job):
        return job
            
    def change_rjn_job(self, job):
        return job

    def create_job(self):
        """Returns the relevant job template as a list, then performs the necessary modifications. After, the job file is printed in the appropriate directory."""
        jobfile = self.get_job_template()
        # modify
        if str(self.sc) == 'mgs':
            jobfile = self.change_mgs_job(jobfile)
            jobfile = jobfile.replace('name', f'{self.base_name}') 
        elif str(self.sc) == 'rjn':
            jobfile = self.change_rjn_job(jobfile)
            jobfile = jobfile.replace('name', f'{self.base_name}') 
        elif self.sc == 'mon':
            jobfile = jobfile.replace('base_name', f'{self.base_name}') 
        self.write_file(jobfile, filetype='job')