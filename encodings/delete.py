import pickle

# Buka file faces.pkl
with open("faces.pkl", "rb") as f:
    data = pickle.load(f)

# Cari index nama Reza
target_name = "Muhammad Reza Hifzar"

if target_name in data["names"]:
    index = data["names"].index(target_name)

    # Hapus data berdasarkan index yang sama
    del data["names"][index]
    del data["user_ids"][index]
    del data["encodings"][index]

    # Simpan kembali
    with open("faces.pkl", "wb") as f:
        pickle.dump(data, f)

    print(f"{target_name} berhasil dihapus")
else:
    print("Nama tidak ditemukan")