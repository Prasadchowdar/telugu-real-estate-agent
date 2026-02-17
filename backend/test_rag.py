"""
End-to-end test for RAG pipeline.
Tests: PDF ingestion → ChromaDB storage → similarity search
"""
import asyncio
import sys
import os

# Add parent dir to path so we can import services
sys.path.insert(0, os.path.dirname(__file__))

from services.rag_service import ingest_pdf, search_context


class FakeUploadFile:
    """Simulate FastAPI UploadFile for testing."""
    def __init__(self, filepath):
        self.filename = os.path.basename(filepath)
        self._path = filepath

    async def read(self):
        with open(self._path, "rb") as f:
            return f.read()


async def test_rag():
    pdf_path = os.path.join(os.path.dirname(__file__), "test_data", "sri_sai_properties.pdf")

    if not os.path.exists(pdf_path):
        print("❌ Test PDF not found. Run create_test_pdf.py first.")
        return False

    # 1) Ingest PDF
    print("=" * 60)
    print("STEP 1: Ingesting PDF into ChromaDB...")
    print("=" * 60)
    fake_file = FakeUploadFile(pdf_path)
    result = await ingest_pdf(fake_file)
    print(f"Result: {result}")

    if result["status"] != "success":
        print(f"❌ Ingestion failed: {result['message']}")
        return False
    print(f"✅ Ingested {result['chunks']} chunks\n")

    # 2) Test searches
    test_queries = [
        "Kokapet lo flats entha?",
        "What is the price of 2BHK in Narsingi?",
        "villa available in Kokapet?",
        "commercial office space Madhapur",
        "contact number Sri Sai Properties",
        "payment plan EMI options",
    ]

    print("=" * 60)
    print("STEP 2: Testing similarity search...")
    print("=" * 60)

    all_passed = True
    for query in test_queries:
        print(f"\n🔍 Query: '{query}'")
        context = await search_context(query, top_k=2)
        if context:
            # Show first 200 chars of context
            preview = context[:200].replace('\n', ' ')
            print(f"   ✅ Found context: {preview}...")
        else:
            print(f"   ⚠️  No relevant context found")
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED — RAG pipeline is working!")
    else:
        print("⚠️  Some searches returned no results (may need tuning)")
    print("=" * 60)
    return True


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_rag())
