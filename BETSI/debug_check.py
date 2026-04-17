import pandas as pd
df = pd.read_excel("Data/Material_Database.xlsx", sheet_name="Components")
rows = df[df.iloc[:,0].astype(str).str.contains("EXT_WALL_STRUCTURE", na=False)]
print(rows[["Component Code","Layers","Layer Index"]].to_string())
