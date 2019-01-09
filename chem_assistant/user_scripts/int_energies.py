__all__ = ['calculate_interaction_energies']

import csv
import re
from ..core.molecule import Molecule
# pandas is slow, maybe try something different?

def group_files(csv, header = True):
    """
    Parses a csv file produced by python script
    """

    def split_path(path):
        """
        Returns two strings- one upto the molecule directory, the other further into it.
        Example: c4mim/ac/4/p2/spec/frags/water_4/ --> 
        c4mim/ac/4/p2, spec/frags/water_4

        - Data pre-processing
        """
        upto = 0
        path_split = path.split('/')
        for ind, part in enumerate(path_split):
            if part in ('opt', 'spec', 'hess'):
                upto = ind
                break
        
        if upto != 0:
            path_to_mol = path_split[0: upto]
            path_to_each_calc = path_split[upto + 1:]
            
        path_to = '/'.join(path_to_mol)
        path_after_run = '/'.join(path_to_each_calc)
        return path_to, path_after_run


    groups = {}   
    with open(csv, "r") as f:
        if header:
            file_obj = f.readlines()[1:]
        else:
            file_obj = f.readlines

        for line in file_obj:
            file, path, basis, hf, mp2 = line.split(',')
            # split path
            molecule, path_to_file = split_path(path)
            file = path_to_file + '/' + file      
            if molecule not in groups:
                groups[molecule] = [[file, basis, hf, mp2]]
            else:
                groups[molecule].append([file, basis, hf, mp2])# need to be lists, as later, add on a frag term


    return groups

def calculate_energies(d):
    """
    Calculates interaction energies from single point energy calculations
    INT = E_COMPLEX - SUM(E_ION)
    INT_NEUTRAL SPECIES = E_COMPLEX - E_IONIC_CLUSTER - SUM(E_NEUTRAL_SPECIES)
    """

    def calc_results_per_system(system):
        results_dict = {}
        for job in system:
            resulta_dict[path] = calc_results_per_job(job)


    def calc_results_per_job(job, results_dict):
        complex_hf = 0.0
        complex_mp2 = 0.0
        sum_frag_hf = 0.0
        sum_frag_mp2 = 0.0
        ionic_hf = 0.0
        ionic_mp2 = 0.0
        sum_neu_hf = 0.0
        sum_neu_mp2 = 0.0
            
        file, basis, hf, mp2 = job

        # find type of system
        name = '/'.join(file.split('/')[:-1])
        if 'frags' in name:
            job.append('frag')
            for mol in Molecule.Neutrals:
                if mol in name:
                    job.append('neutral')
        if 'ionic' in name:
            job.append('ionic')
        if 'complex' in name:
            job.append('complex')
        
        if 'complex' in job:
            _, _, hf, mp2, _ = job
            hf, mp2 = map(float, (hf, mp2))
            complex_hf = hf
            complex_mp2 = mp2
        
        if 'ionic' in job:
            _, _, hf, mp2, _ = job
            hf, mp2 = map(float, (hf, mp2))
            ionic_hf = hf
            ionic_mp2 = mp2

        if 'frag' in job:
            if 'neutral' in job:
                _, _, hf, mp2, _, _ = job
                hf, mp2 = map(float, (hf, mp2))
                sum_neu_hf += hf
                sum_neu_mp2 += mp2
                sum_frag_hf += hf
                sum_frag_mp2 += mp2
            else:
                _, _, hf, mp2, _, = job
                hf, mp2 = map(float, (hf, mp2))
                sum_frag_hf += hf
                sum_frag_mp2 += mp2



        elec_hf = (complex_hf - sum_frag_hf) * 2625.5
        elec_mp2 = (complex_mp2 - sum_frag_mp2) * 2625.5

        print(elec_hf, elec_mp2)
        # disp_hf = 0.0
        # disp_mp2 = 0.0
        # if ionic_hf != 0.0: #then reassign
        #     disp_hf = (complex_mp2 - ionic_hf - sum_neu_hf) * 2625.5
        #     disp_mp2 = (complex_mp2 - ionic_mp2 - sum_neu_mp2) * 2625.5

        # total_hf = elec_hf + disp_hf # always apply- if no neutral molecules, then disp_hf = 0
        # total_mp2 = elec_mp2 + disp_mp2

        # electro = (total_hf / total_mp2) * 100
        # disp = total_mp2 - total_hf

        # if ionic_hf != 0.0:
        #     purely_ionic = False
        #     return {'elec_hf': elec_hf, 'elec_mp2': elec_mp2, 'disp_hf': disp_hf, 'disp_mp2': disp_mp2, 'total_hf': total_hf, 'total_mp2': total_mp2, 'disp': disp, 'electro': electro} # all the neutral stuff
        # else:
        #     return {'total_hf': total_hf, 'total_mp2': total_mp2, 'disp': disp, 'electro': electro}

            # separate out purely ionic interaction energies from mixed

    purely_ionic = True
    results_dict = {}
    for k, v in d.items():
        print(k, v)
    #     for job in v:
    #         file = job[0]
    #         if 'spec' in file: # spec
    #             results_dict[k] = calc_results(job, results_dict)

    # for val in results_dict.values():
    #     if len(val) > 4:
    #         purely_ionic = False
    # return results_dict, purely_ionic


def write_csv(data, purely_ionic, filename):

    if purely_ionic:
        col_names = ('Path', 'Cation', 'Anion', 'Total Int_HF [kJ/mol]', 'Total Int_MP2 [kJ/mol]', 'Dispersion [kJ/mol]', '% Electrostatics', 'Rank', 'ΔE [kJ/mol]')

        variables = ('total_hf', 'total_mp2', 'disp', 'electro', 'rank', 'deltaE')
    else:
        col_names = ('Path', 'Cation', 'Anion', 'Elec Int_HF [kJ/mol]', 'Elec Int_MP2 [kJ/mol]', 'Disp Int_HF [kJ/mol]', 'Disp Int_MP2 [kJ/mol]', 'Total Int_HF [kJ/mol]', 'Total Int_MP2 [kJ/mol]' 'Dispersion [kJ/mol]', '% Electrostatics', 'Rank', 'ΔE [kJ/mol]')

        variables = ('elec_hf', 'elec_mp2', 'disp_hf', 'disp_mp2', 'total_hf', 'total_mp2', 'disp', 'electro', 'rank', 'deltaE')
    
    def update_csv(path, cat, an, d, variables):
        locals().update(d) #create variables
        lst = [path, cat, an]
        for key in variables:
            lst.append(locals()[key])
        return lst

    with open(filename, "w", encoding = 'utf-8-sig') as new:
        writer = csv.writer(new)
        # writer.writerow(('Int_MP2 = SRS interaction energies if possible',))
        writer.writerow(col_names)
        for cation in data:
            for anion in data[cation]:
                for path, d in data[cation][anion].items():
                    numbers = update_csv(path, cation, anion, d, variables)
                    writer.writerow(numbers)
            
            
def sort_data(data):
    """ 
    Adds a -1 to the first configuration of each IL, if not already there, then sorts the data into alphanumerical order
    """
    collapsed = [[k, v] for k, v in data.items()]
    sorted_data = sorted(collapsed, key = lambda kv: kv[0])
    sorted_dict  = {}
    for data in sorted_data:
        k, v = data
        sorted_dict[k] = v # as of py 3.6, dicts remain ordered- so no need to implement ordered dict
    return sorted_dict

def assign_molecules(data):
    """ 
    Assign a cation and anion to each path.
    """
    for key in data.keys():
        cation = ''
        anion = ''
        vals = key.split('/')
        for val in vals:
            # different names for the same anion
            if val == 'ch':
                val = 'choline'
            if val == 'ac':
                val = 'acetate'
            if val == 'h2po4':
                val = 'dhp' # in Molecules.Anions
            if val == 'mesylate':
                val = 'mes'
            if val in Molecule.Cations:
                cation = val
            elif val in Molecule.Anions:
                anion = val
        data[key]['cation'] = cation
        data[key]['anion'] = anion
    return data

def rank_configs(data):
    """
    Ranks each configuration according to its interaction energies.
    """

    # create groups
    cations = sorted(set([v['cation'] for v in data.values()]))
    anions  = sorted(set([v['anion']  for v in data.values()]))
    # add to groups in alphabetical order

    groups = {}
    for c in cations:
        groups[c] = {}
        for a in anions:
            groups[c][a] = {}

    # add data to correct bin
    for k, v in data.items():
        for cation in cations:
            for anion in anions:
                if cation == v['cation'] and anion == v['anion']:
                    groups[cation][anion][k] = v
    
    for cation in groups:
        for anion in groups[cation]:
            energies = []
            for path, data in groups[cation][anion].items():
                energies.append((path, data['total_mp2']))
            sorted_vals = sorted(energies, key = lambda tup: tup[1]) #sort on the energies
            for index, val in enumerate(sorted_vals, 1): #start index at 1
                path, energy = val
                groups[cation][anion][path]['rank'] = index
                groups[cation][anion][path]['deltaE'] = groups[cation][anion][path]['total_mp2'] - sorted_vals[0][1] # minimum energy

    # change the order of the paths of each config in the groups dict for each cation-anion pair, by their rank

    ordered_dict = {}
    for cat in groups:
        ordered_dict[cat] = {}
        for an in groups[cat]:
            ordered_dict[cat][an] = {}
            lst = [(k, v) for k, v in groups[cat][an].items()]
            sorted_lst = sorted(lst, key = lambda kv: kv[1]['rank'])
            for kv in sorted_lst:
                k, v = kv
                ordered_dict[cat][an][k] = v 
    return ordered_dict

def calculate_interaction_energies(csv):
    """
    Calculate interaction energies from a csv file created with this python script; the function
assumes that variables will be present in the csv.
    """
    data = group_files(csv)
    new_data, purely_ionic = calculate_energies(data)
    sorted_data = sort_data(new_data)
    assigned = assign_molecules(sorted_data)
    ranked = rank_configs(assigned)
    correct = False
    while not correct:
        filename = input('Filename of output: ')
        if not filename.endswith('.csv'):
            print("Please end the filename in '.csv'")
        else:
            correct = True
    write_csv(ranked, purely_ionic, filename)
