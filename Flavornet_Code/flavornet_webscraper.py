# Python script to scrape flavornets.org and generate a CSV, and add SMILES representations for each molecule

from pathlib import Path
from bs4 import BeautifulSoup
import csv
from urllib.request import urlopen
from rdkit import Chem
from rdkit.Chem import rdMolDescriptors


def flavornet_data():
    # function to scrape the website
    
    odors_and_odorants = []
    property_names = []

    soup = BeautifulSoup(open('odorants.html'), 'html.parser')

    odorant_tags = soup.findAll('td', {'class': 'ch'})
    odor_tags = soup.findAll('td', {'class': 'sm'})

    #print(len(odor_tags), len(odorant_tags))   #738 molecules, first row is empty

    for index in range(1, len(odor_tags)):
        odorant = odorant_tags[index].text.strip('\n')  # Get the odorant from the tag and strip newline from the name
        odorant = odorant.strip(',')  # Strip leading and trailing commas from the molecule name
        odorant = odorant.replace(" ", "")  # Clean up spaces
        odorant= replace_unicode(odorant)  # Replace greek symbols with names

        odor = odor_tags[index].text  # Get the odor from the tag
        SMILES = molecule_to_smiles(odorant)  # Get the SMILES representation for the molecule

        """ Getting the molecular properties for the odorant """
        if SMILES != '0':
            property_names, properties = getChemicalProperties(SMILES)

        if index % 10 == 0:
            print("Finished %d molecules" % index)

        temp = [odorant, odor, SMILES] + properties
        odors_and_odorants.append(temp)


    # Write to csv file
    data_folder = Path('../Datasets/')
    file_to_open = data_folder/'flavornet_dataset.csv'
    create_CSV(file_to_open, odors_and_odorants, property_names)


def create_CSV(file, odors_and_odorants, properties):
    # Function to write the scraped data to the CSV
    with open(file, 'w+') as file:
        header = ['Odorant', 'Odor', 'SMILES representation'] + properties
        writer = csv.writer(file)
        writer.writerow(header)
        writer.writerows(odors_and_odorants)


def replace_unicode(molecule):
    # A function to replace greek symbols with their names
    alpha_unicode = u"\u03B1"
    beta_unicode = u"\u03B2"
    gamma_unicode = u"\u03B3"
    delta_unicode = u"\u03B4"

    molecule = molecule.replace(alpha_unicode, "alpha").replace(beta_unicode, "beta").replace(gamma_unicode, "gamma").replace(delta_unicode, "delta")
    return molecule


def molecule_to_smiles(molecule):
    # A function that gives you the SMILES representation of a molecule
    try:
        url = 'https://cactus.nci.nih.gov/chemical/structure/' + molecule + '/smiles'
        SMILES = urlopen(url).read().decode('utf8')
        return SMILES
    except:
        # If there is no SMILES representation, for whatever reason
        return 0


def getChemicalProperties(SMILE):
    # A functions that uses RDKit to generate chemical properties from SMILES representation
    property_names = []
    properties = []
    try:
        molecule = Chem.MolFromSmiles(SMILE)
        generate_properties = rdMolDescriptors.Properties()
        for name, value in zip(generate_properties.GetPropertyNames(), generate_properties.ComputeProperties(molecule)):
            property_names.append(name)
            properties.append(value)

        return property_names, properties

    except:
        return ["N/A"]*25, ["N/A"]*25  # RDKit gives you 25 properties


if __name__ == '__main__':
    flavornet_data()