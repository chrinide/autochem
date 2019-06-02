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
    def __init__(self, using = None, frags_in_subdir = False, settings = None, filename = None, is_complex = False, run_dir = None):
        super().__init__(using)
        self.filename = filename
        self.defaults = read_template('psi.json') #settings object 
        if settings is not None:
            # can only have one run type, currently- need to delete the energy if running an
            # optimisation, for example
            if 'run' in settings.input.keys():
                del self.defaults.input.run
            self.merged = self.defaults.merge(settings) # merges inp, job data 
            self.input = self.merged.input
            self.job = self.merged.job
        else:
            self.input = self.defaults.input
        if '/' in using:
            self.title = using.split('/')[-1][:-4] #say using = ../xyz_files/file.xyz --> 
        else:
            self.title = using[:-4]

        if run_dir is not None:
            self.made_run_dir = True
        else:
            self.made_run_dir = False
         
        
        self.is_complex = is_complex # creates a `complex` dir

        self.create_inp()
        self.create_job()
        self.make_run_dir()
        self.place_files_in_dir()
        if frags_in_subdir:
            self.create_inputs_for_fragments()

    def make_run_dir(self):
        if not self.made_run_dir: # only do it once
            mkdir(self.base_name) # make opt/spec/hessin parent dir
            self.made_run_dir = True
        
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

    def write_file(self, data, filetype):
        """Writes the generated PSI4 input/jobs to a file. If no filename is passed when the class is instantiated, the name of the file defaults to the run type: a geometry optimisation (opt), single point energy calculation (spec), or a hessian matrix calculation for vibrational frequencies (freq). 
        NOTE: Must pass data as a string, not a list!""" 
        with open(f"{self.base_name}.{filetype}", "w") as f:
            f.write(data)


    def create_inp(self):
        self.make_header()
        self.add_unbound()
        self.add_globals()
        self.add_run()
        self.file_basename()
        self.write_file(self.inp, filetype = 'inp')

    def get_job_template(self):
        job_file = self.find_job()
        with open(job_file) as f:
            job = f.read()       
            return job

    def create_job(self):
        """Returns the relevant job template as a list, then performs the necessary modifications. After, the job file is printed in the appropriate directory."""
        jobfile = self.get_job_template()
        # modify
        if str(self.sc) == 'mgs':
            jobfile = jobfile.replace('name', f'{self.base_name}') 
        elif str(self.sc) == 'rjn':
            # should alter the job time as they never need 4 hours- 
            # walltime = max_time_for_4ip (probs have?) * num atoms / num atoms in 4IP
            jobfile = jobfile.replace('name', f'{self.base_name}') 
        elif str(self.sc) == 'mon':
            jobfile = jobfile.replace('name', f'{self.base_name}') 
        elif str(self.sc) == 'stm':
            jobfile = jobfile.replace('name', f'{self.base_name}') 
        self.write_file(jobfile, filetype='job')        

    def place_files_in_dir(self):
        """Move input and job files into a directory named with the input name (``base_name``) i.e.
        moves opt.inp and opt.job into a directory called ``opt``."""
        if self.is_complex:
            if not exists(join('complex', self.base_name)):
                mkdir('complex')
                mkdir(join('complex', self.base_name))
                # copy the xyz over from the parent dir - only one xyz in the dir, but no idea of the name- if _ in the name, the parent dir will be a number, or it might be the nsame of the complex? 
                system('cp *.xyz complex/complex.xyz')
            system(f'mv {self.base_name}.inp {self.base_name}.job complex/{self.base_name}/')
        else:
            if not exists(self.base_name):    
                mkdir(self.base_name)
            system(f'mv {self.base_name}.inp {self.base_name}.job {self.base_name}/')

    def create_inputs_for_fragments(self):
        """Very useful to generate files for each fragment automatically, for single point and frequency calculations, generating free energy changes. Called if ``frags_in_subdir`` is set to True, as each fragment is given a subdirectory in an overall subdirectory, creating the following directory structure (here for a 5-molecule system):
            .
            ├── frags
            │   ├── acetate0
            │   │   ├── acetate0.xyz
            │   │   └── spec.inp
            │   ├── acetate1
            │   │   ├── acetate1.xyz
            │   │   └── spec.inp
            │   ├── choline2
            │   │   ├── choline2.xyz
            │   │   └── spec.inp
            │   ├── choline3
            │   │   ├── choline3.xyz
            │   │   └── spec.inp
            │   └── water4
            │       ├── spec.inp
            │       └── water4.xyz
            ├── spec.inp
        """
        # not necessarily any splitting prior to this
        self.is_complex = False
               
        # if self.merged.nfrags != {}: #automatically creates an empty dict if called
        #     self.mol.nfrags = self.merged.nfrags
        # else:
        #     self.mol.nfrags = int(input('Number of fragments: '))

        self.mol.separate() #creating frags 
        #look over self.mol.fragments, generate inputs- make a settings object with the desired features
        
        # after separation- create another frag with the ionic cluster!

        #make subdir if not already there
        subdirectory = join(getcwd(), 'frags')
        if not exists(subdirectory):
            mkdir(subdirectory)

        parent_dir = getcwd()
        count = 0 #avoid  overwriting files by iterating with a number
        for frag, data in self.mol.fragments.items():
            if data['frag_type'] == 'frag':
                #make a directory inside the subdir for each fragment
                name = f"{data['name']}_{count}" # i.e. acetate0, acetate1, choline2, choline3, water4
                if not exists(join(subdirectory, name)):
                    mkdir(join(subdirectory, name)) # ./frags/water4/
                chdir(join(subdirectory, name))
                Molecule.write_xyz(self, atoms = data['atoms'], filename = name + str('.xyz')) #using the method, but with no class
                
                #use the same settings, so if runtype is freq, generate freq inputs for all fragments too.
                if hasattr(self, 'merged'):
                    frag_settings = self.merged
                else:
                    frag_settings = self.defaults
                frag_settings.input.molecule.charge = data['charge']
                if data['multiplicity'] != 1:
                    frag_settings.input.molecule.multiplicity = data['multiplicity']
                job = PsiJob(using = name + str('.xyz'), settings=frag_settings, run_dir = True) 
                chdir(parent_dir)
                count += 1
        if hasattr(self.mol, 'ionic'):
            # only 1 ionic network        
            subdir_ionic = join(getcwd(), 'ionic')
            if not exists(subdir_ionic):
                mkdir(subdir_ionic)
            chdir(subdir_ionic)
            write_xyz(atoms = self.mol.ionic['atoms'], filename = 'ionic.xyz')
        
            # re-use settings from complex
            if hasattr(self, 'merged'):
                frag_settings = self.merged
            else:
                frag_settings = self.defaults
            frag_settings.input.molecule.charge = self.mol.ionic['charge']
            if self.mol.ionic['multiplicity'] != 1:
                frag_settings.input.molecule.multiplicity = self.mol.ionic['multiplicity']
            job = PsiJob(using = 'ionic.xyz', settings=frag_settings, run_dir = True) 
            chdir(parent_dir)
