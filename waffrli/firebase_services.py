
from waffrliApp.settings import db

def get_document(collection, document_id):
    """Retrieve a document from Firestore."""
    doc_ref = db.collection(collection).document(document_id)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    return None

def add_document(collection, data, document_id=None):
    """Add a document to Firestore."""
    if document_id:
        db.collection(collection).document(document_id).set(data)
        return document_id
    else:
        doc_ref = db.collection(collection).add(data)
        return doc_ref[1].id

def update_document(collection, document_id, data):
    """Update a document in Firestore."""
    db.collection(collection).document(document_id).update(data)
    
def delete_document(collection, document_id):
    """Delete a document from Firestore."""
    db.collection(collection).document(document_id).delete()

def query_collection(collection, filters=None, order_by=None, limit=None):
    """Query a collection with optional filters, ordering, and limit."""
    query = db.collection(collection)
    
    # Apply filters if provided
    if filters:
        for field, operator, value in filters:
            query = query.where(field, operator, value)
    
    # Apply ordering if provided
    if order_by:
        field, direction = order_by if isinstance(order_by, tuple) else (order_by, 'ASCENDING')
        query = query.order_by(field, direction=direction)
    
    # Apply limit if provided
    if limit:
        query = query.limit(limit)
    
    # Execute query and return results
    return [doc.to_dict() for doc in query.stream()]