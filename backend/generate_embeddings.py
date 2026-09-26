from app.services.embedding_generator import generate_product_embeddings


if __name__ == "__main__":
    count = generate_product_embeddings()

    print()
    print(f"Generated embeddings: {count}")