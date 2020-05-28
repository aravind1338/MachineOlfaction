from pathlib import Path
from bs4 import BeautifulSoup
import csv

odors_and_odorants = []

soup = BeautifulSoup(open('odorants.html'), 'html.parser')

odorant_tags = soup.findAll('td', {'class': 'ch'})
odor_tags = soup.findAll('td', {'class': 'sm'})

#print(len(odor_tags), len(odorant_tags))   #738 molecules, first row is empty

for index in range(1, len(odor_tags)):
    odorant = odorant_tags[index].text.strip('\n') # Get the odorant from the tag and strip newline from the name
    odor = odor_tags[index].text # Get the odor from the tag

    temp = [odorant, odor]
    odors_and_odorants.append(temp)


# Write to csv file
data_folder = Path('../Datasets/')
file_to_open = data_folder/'flavornet_dataset.csv'
with open(file_to_open, 'w+') as file:
    header = ['Odorant', 'Odor']
    writer = csv.writer(file)
    writer.writerow(header)
    writer.writerows(odors_and_odorants)


