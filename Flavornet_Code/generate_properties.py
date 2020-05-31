from rdkit import Chem
print(Chem.MolToSmiles(Chem.MolFromSmiles('C1=CC=CN=C1')))