from app.agents.semantic_classifier import (
    classify_concept
)

def main():

    concepts = [
        "Heart rate",
        "Body Weight",
        "Hemoglobin A1c/Hemoglobin.total in Blood",
        "Creatinine [Mass/volume] in Serum or Plasma",
        "Cholesterol in HDL [Mass/volume] in Serum or Plasma"
    ]

    for concept in concepts:

        print("\n" + "=" * 50)
        print(f"Testing: {concept}")
        print("=" * 50)

        result = classify_concept(concept)

        print(result)

if __name__ == "__main__":
    main()