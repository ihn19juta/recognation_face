import pickle

data = {
    "encodings": [],
    "names": []
}

with open("encodings/faces.pkl", "wb") as f:
    pickle.dump(data, f)

print("faces.pkl berhasil dibuat")
