import pickle

with open("faces.pkl", "rb") as f:
    data = pickle.load(f)

print("Names:", data["names"])
print("User IDs:", data["user_ids"])
print("Jumlah wajah:", len(data["encodings"]))