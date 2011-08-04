function(doc) {

	if (doc.doc_type != "resource_data") return;
	
	var date_stamp = doc.node_timestamp;
	date_stamp = date_stamp.substring(0,10);
	var people = new Array();
	
	var arrayContains = function(testArray, testValue) {
		for each(var val in testArray) {
			if(val==testValue) return true;
		}
		return false;
	}	
	
	//grab all the people in identity or submitter (depending on version)
	if(doc.identity) {
		if(doc.identity.submitter) people.push(doc.identity.submitter.toLowerCase());
		if(doc.identity.curator) people.push(doc.identity.curator.toLowerCase());
		if(doc.identity.owner) people.push(doc.identity.owner.toLowerCase());
		if(doc.identity.signer) people.push(doc.identity.signer.toLowerCase());
	}
	if(doc.submitter) people.push(doc.submitter.toLowerCase());
	

	//build people indices
	for each(person in people) {
		emit(person, doc.doc_ID);
	}
	
	//build date indices
	emit(date_stamp, doc.doc_ID);
	for each(person in people) {
		emit([date_stamp, person], doc.doc_ID);
	}
	
	//build
	var emitaAllKeywordIndices = function(value) {
		emit(value, doc.doc_ID);
		for each(person in people) {
			emit([person, value], doc.doc_ID);
		}
		emit([date_stamp, value], doc.doc_ID);
		for each(person in people) {
			emit([date_stamp, person, value], doc.doc_ID);
		}
	}

	var usedKeys = new Array();
	for each(var key in doc.keys) {
		var cleanKey = key.toLowerCase();
		cleanKey = cleanKey.replace(/^\s+/, "");
		cleanKey = cleanKey.replace(/\s+$/, "");
		//var used = arrayContains(usedKeys, key);
		if(!arrayContains(usedKeys, cleanKey)) {
			emitaAllKeywordIndices(cleanKey);
			usedKeys.push(cleanKey);
		}
		
	  }
	
	for each(var schema in doc.payload_schema) {
		emitaAllKeywordIndices(schema);
	}
	
	if(doc.resource_data_type) emitaAllKeywordIndices(doc.resource_data_type);
	
}