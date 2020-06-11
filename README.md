# MachineOlfaction
Code associated with the machine olfaction research project. Will add more stuff soon


Requirements:

Almost all the required libraries for the project are in requirements.txt, except for RDKit. That package cannot be downloaded via pip, and the easiest way to get it is through conda (https://www.rdkit.org/docs/Install.html).


flavornet_webscraper.py:

To extract the dataset from flavornets.org, I copied the source HTML (right click, view frame source) and used a webscraper to get the dataset.

Running it once will give you flavornet_dataset.csv, a CSV file that mimics the website along with the SMILES representation of the molecules and 25 molecular properties associated generated using RDKit

flavornet_analysis.ipynb

Code for visualizing the data (connection strength, distribution of labels, correlation matrix)