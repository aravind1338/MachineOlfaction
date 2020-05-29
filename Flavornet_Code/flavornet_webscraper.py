# Python script to scrape flavornets.org and generate a CSV, and add SMILES representations for each molecule

from pathlib import Path
from bs4 import BeautifulSoup
import csv
from urllib.request import urlopen


# function to scrape the website
def flavornet_data():

    odors_and_odorants = []

    soup = BeautifulSoup(open('odorants.html'), 'html.parser')

    odorant_tags = soup.findAll('td', {'class': 'ch'})
    odor_tags = soup.findAll('td', {'class': 'sm'})

    #print(len(odor_tags), len(odorant_tags))   #738 molecules, first row is empty

    for index in range(1, len(odor_tags)):
        odorant = odorant_tags[index].text.strip('\n') # Get the odorant from the tag and strip newline from the name
        odorant = odorant.strip(',') # Strip leading and trailing commas from the molecule name
        odor = odor_tags[index].text # Get the odor from the tag
        SMILES = molecule_to_smiles(odorant.replace(" ", ""))  # Get the SMILES representation for the molecule

        temp = [odorant, odor, SMILES]
        odors_and_odorants.append(temp)


    # Write to csv file
    data_folder = Path('../Datasets/')
    file_to_open = data_folder/'flavornet_dataset.csv'
    with open(file_to_open, 'w+') as file:
        header = ['Odorant', 'Odor', 'SMILES representation']
        writer = csv.writer(file)
        writer.writerow(header)
        writer.writerows(odors_and_odorants)


# A function that gives you the SMILES representation of a molecule
def molecule_to_smiles(molecule):
    try:
        url = 'https://cactus.nci.nih.gov/chemical/structure/' + molecule + '/smiles'
        SMILES = urlopen(url).read().decode('utf8')
        return SMILES
    except:
        # If there is no SMILES representation, for whatever reason
        return 0


if __name__ == '__main__':
    flavornet_data()