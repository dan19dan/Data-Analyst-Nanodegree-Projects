# -*- coding: utf-8 -*-
"""
Created on Mon Aug 24 01:25:59 2015

@author: Administrator

Data Wrangling project 2
"""

import xml.etree.ElementTree as ET
import re
import pprint
import pandas as pd
import math
import nltk
import time
import os
import pickle
from unidecode import unidecode
from pymongo import MongoClient

import sys
sys.path.append("./atd")
import ATD

#Functions
def words_process():
    sort_words()
    search_for_typos()
    filter_typos()

def save_changes():
    print "Applying corrections to words_dict"
    print "Size of words_dict before changes: {0}".format(len(words_dict.keys()))
    for typo in corrections_dict:
        if typo in words_dict.keys():
            correction = corrections_dict[typo]
            if correction in words_dict.keys():
                words_dict[correction] += words_dict[typo]
                del words_dict[typo]
            
    print "Size of words_dict after changes: {0}".format(len(words_dict.keys()))      
      
    #words_dict = get_words(words_dict)
    #words = words_dict.keys
    
    
    print "Applying correction to misspelled words in tags"
    tags_to_modify = ['name', 'addr:street']
    for key in tag_texts_dict.keys():
        if key in tags_to_modify:
            for tag in tag_texts_dict[key].keys():
                temp_tag = apply_word_corrections(tag)
                if temp_tag != tag:
                    if temp_tag not in tag_texts_dict[key].keys():
                        tag_texts_dict[key][temp_tag] = tag_texts_dict[key][tag]
                         
                    else:
                        tag_texts_dict[key][temp_tag] += tag_texts_dict[key][tag]
                    del tag_texts_dict[key][tag]
                
    print "Get a list of all documents"
    docs = {}
    for key in tag_texts_dict.keys():
        for tag in tag_texts_dict[key]:
            for id_num in tag_texts_dict[key][tag]:
                if id_num not in docs.keys():
                    docs[id_num] = {}
                docs[id_num][key] = tag
                
    ids_list = docs.keys()
    ids_list.sort()
    documents = zmg_collection.find({'id': { '$in' : ids_list} })
    
    
    print "Checking for modified documents"
    changed_docs = []
    for document in documents:
        save = False
        for key in document.keys():
            if key == 'address':
                for addr_key in document['address'].keys():  
                    original_key = 'addr:' + addr_key
                    if key in docs[document['id']].keys():
                        if document[key][addr_key] != docs[document['id']][original_key]:
                            document[key][addr_key] = docs[document['id']][original_key]
                            save = True
            
            if key in docs[document['id']].keys():
                if document[key] != docs[document['id']][key]:
                    document[key] = docs[document['id']][key]
                    save = True
        
        if save:
            changed_docs.append(document)
    
    documents = []
    print "Saving {0} documents".format(len(changed_docs))
    for document in changed_docs:    
        zmg_collection.save(document)
    client.close()
    
def open_file(filename,object_type):
    #In process that I don't wanted to repead each time I executed the program
    #saved the results as pickle files, this functions search for the file
    #or inserts an empty object if the file doesn't exists.
    if os.path.exists(filename):
        lcl_object = pickle.load( open(filename, "rb") )
    else:
        lcl_object = object_type
        
    return lcl_object

def filter_typos():    
    global possible_typos_list
    
    for word in possible_typos:
        possible_typos_list.append(word)
        possible_typos_list += possible_typos[word]
    
        possible_typos_list = list(set(possible_typos_list))
    
    
    for word in  possible_typos_list:
        if word in words_dict.keys():
            if words_dict[word] < 4:
                typos_prob[word] = words_dict[word]
    
    possible_typos_list = typos_prob.keys() 
    
    print "Consulting After the Deadline webservice"
    ATD.setDefaultKey("dnava2cac04bcd5e1f7b3749e4fc8107f4f72")
    
    
    for possible_typo in possible_typos_list:
        if possible_typo in consulted:
            continue
        
        if isinstance(possible_typo,unicode):
            word = possible_typo.encode('UTF-8')
        else:
            word = possible_typo
        
        append = True
        for language in ['es', 'en']:
            if language == 'en' and isinstance(word.decode('UTF-8'),unicode):
                word = unidecode(word.decode('UTF-8'))
            ATD.setLanguage(language)
            time.sleep(5)
            try:
                errors = ATD.checkDocument(word)
            except Exception as e:
                pickle.dump( consulted, open( consulted_file, "wb" ) )
                pickle.dump( typos, open( typos_file, "wb" ) )
                time.sleep(30)
                errors = ATD.checkDocument(word)
                
            if errors:
                for error in errors:
                    
                    if len(error.suggestions) > 0:
                        
                        for correction in error.suggestions:
                            if word.lower() == correction.lower():
                                append = False
                            if isinstance(correction,unicode):
                                if word.lower() == unidecode(correction.lower()):
                                    corrections_from_atd[word] = correction
            else:
                append = False
    
            if len(errors) == 0:
                append = False
                
            if not append:
                break
            
            
        if append:
            if possible_typo not in typos:
                typos.append(possible_typo)
        consulted.append(possible_typo)                    
                    
    
    pickle.dump( consulted, open( consulted_file, "wb" ) )
    pickle.dump( typos, open( typos_file, "wb" ) )
    pickle.dump( corrections_from_atd, open( corrections_from_atd_file, "wb" ) )



    #ATD webservice doesn't contains common people name or places.
    #So I downloaded a dump from geonames.org webservice to cross-validate,
    #if a word is really a word or just a typo.
    places  = get_places_and_names()
    print "Cross-validating with geonames"
    print "{0} typos before".format(len(typos))
    for word in typos:
        if word.encode("UTF-8") in places.keys():
            typos.remove(word)
    print "{0} typos after".format(len(typos))


    #If a word was deleted by the pass filters, it means that at some point
    #it was determined to be correct. And if a word is still in typos list
    #at this point, means that the previous steps failed to determine if
    #it is a valid, correctly spelled word.
    for word in possible_typos:
        if word in typos:
            typos_dict[word] = possible_typos[word]
        else:
            for possible_correction in possible_typos[word]:
                if possible_correction in typos:
                    if word not in typos_dict.keys():
                        typos_dict[word] = []
                    typos_dict[word].append(possible_correction)
                

    #Copying corrections from ATD
    for word in corrections_from_atd:
        if type(corrections_from_atd[word]) == list:
            corrections_dict[word] = corrections_from_atd[word][0].capitalize()
        else:
            corrections_dict[word] = corrections_from_atd[word].capitalize()
    
    
    #At this point I have a dict called typos_dict with holds words and their
    #possible correction, but I don't know if the correction is in the key or
    #in the value, this section of the program determines which is the correction
    #and which is in the typo and uses the function select_corrections to make
    #automatic corrections.
    for word in typos_dict.keys():
        if word in typos:
            for possible_solution in typos_dict[word]:
                if possible_solution not in typos:
                    if word not in corrections_dict.keys():
                        if select_corrections(word,possible_solution,manual_corrections):
                            corrections_dict[word] = possible_solution
                            if word in typos_dict.keys():
                                del typos_dict[word]
        else:
            for misspelled in typos_dict[word]:
                if misspelled in typos:
                    if misspelled not in corrections_dict.keys():
                        if select_corrections(misspelled,word,manual_corrections):
                            corrections_dict[misspelled] = word
                            if word in typos_dict.keys():
                                del typos_dict[word]    
    
    pickle.dump( manual_corrections, open( manual_corrections_file, "wb" ) )



def sort_words():
    #Creating a dict with the words sorted by size and first letter.
    for word in words_dict:
    #   Abbreviations and acronyms has been analyzed before this point,
    #   so there's no need to include them here.
        if '.' in word:
            continue
        first_letter = word[0]
        word_size = len(word)
        
        if first_letter not in words_abc_size.keys():
            words_abc_size[first_letter] = {word_size : [word]}
            
        else:
            if word_size not in words_abc_size[first_letter]:
                words_abc_size[first_letter][word_size] = []
                
            words_abc_size[first_letter][word_size].append(word)
    

def search_for_typos():
    #Searching for typos with edit_distance.
    '''According to the spanish language grammar, words which finish with a vocal 
    are pluralized with an s at the end, those words are only 1 insert/delete apart
    from each other but aren't typos.
    '''
    vocals = u'aeiouáéíóú'
    print "Check for typos with nltk.metrics.edit_distance"
    for first_letter in words_abc_size:
        if first_letter.islower():
            continue
        for size in words_abc_size[first_letter]:
            if size < 3:
                continue
            for word in words_abc_size[first_letter][size]:
                
                #Check for words with one letter missing.
                if size-1 in words_abc_size[first_letter].keys(): 
                    for smaller_word in words_abc_size[first_letter][size-1]:
                        if nltk.metrics.edit_distance(word, smaller_word) < 2:
                            
                            #Do not count pluralized words
                            if smaller_word[-1] in vocals and word[-1] == 's':
                                continue
                            if word not in possible_typos.keys():
                                possible_typos[word] = []
                            possible_typos[word].append(smaller_word)
                
                word_index = words_abc_size[first_letter][size].index(word)
                
                
                for x in range(word_index,len(words_abc_size[first_letter][size])):
    
                    smaller_word = words_abc_size[first_letter][size][x]
                    if smaller_word == word:
                        continue
                    if nltk.metrics.edit_distance(word, smaller_word,transpositions=True) < 2:
                        
                        if (smaller_word[-1] == u'a' and word[-1] == u'o') \
                        or (smaller_word[-1] == u'o' and word[-1] == u'a') :
                            continue
                        
                        if word not in possible_typos.keys():
                            possible_typos[word] = []
                        possible_typos[word].append(smaller_word)




def select_corrections(typo,possible_correction,manual_corrections = {}):
    #Looking for common typos to make some automatic corrections:
    # - Misspelled words because of similar sounding letters (B and V or S and Z)
    # - Characters typped twice
    # - In Mexican spanish 'si' and 'ci', and 'se' and 'ce' sounds the same, 
    #   it's quite common to see misspelled words because of this.
    qwerty = 'qwertyuiopasdfghjklñzxcvbnm'
    valid_correction = False
    
    #Same length words
    if len(typo) == len(possible_correction):
        
        #Unicode chars related typo"
        if isinstance(possible_correction,unicode):
            if typo == unidecode(possible_correction):
                valid_correction = True
        
        difference = 0
        for i in xrange(len(typo)):
            if typo[i] != possible_correction[i] and difference == 0:
                difference = i

        if typo[difference] in ['j','g'] and possible_correction[difference] in ['j','g']:
            valid_correction = True
        if difference+1 < len(typo):
            if typo[difference] in ['s','c'] \
            and possible_correction[difference] in ['s','c']:
                if ( typo[difference+1] in ['i','e',u'í',u'é'] \
                and possible_correction[difference+1] in ['i','e',u'í',u'é'] ) \
                or (typo[difference+1] == 'h' and possible_correction[difference+1] == 'h'):
                    valid_correction = True
            
            #Typos where two letters where transposed, at this point,
            #The automatically detected correction is very likely 
            #the right correction.
            if typo[difference] == possible_correction[difference+1] \
            and typo[difference+1] == possible_correction[difference]:
                valid_correction = True
        
        #Finding typos related to keyboard configuration.
        if isinstance(possible_correction, unicode):
            letter_correction = qwerty.find(unidecode(possible_correction[difference]))
        else:
            letter_correction = qwerty.find(possible_correction[difference])

        if isinstance(typo, unicode):
            letter_typo = qwerty.find(unidecode(typo[difference]))
        else:
            letter_typo = qwerty.find(typo[difference])   
        
        if abs((letter_typo % 10) - (letter_correction % 10)) < 2:
            if abs((letter_typo / 10) - (letter_correction / 10)) == 1:
                if (letter_typo % 10) == (letter_correction % 10):
                    valid_correction = True
            elif abs((letter_typo / 10) - (letter_correction / 10)) == 0:
                valid_correction = True
        
        
        #Typos related to similar sounding letters.                    
        if re.sub(r'[bv]','%',possible_correction) == re.sub(r'[bv]','%',typo) \
        or re.sub(r'[sz]','%',possible_correction) == re.sub(r'[sz]','%',typo) \
        or re.sub(r'(si)','%',possible_correction) == re.sub(r'[sz]','%',typo):
            valid_correction = True
            
        
    #Different lengths
    else:
        
        #Finding typos related to same letter being typed twice.
        if (not re.search(r'(\w)\1+', possible_correction) and re.search(r'(\w)\1+', typo)) \
        or (not re.search(r'(\w)\1+', typo) and re.search(r'(\w)\1+', possible_correction)):
            valid_correction = True
        
        
        #Manual corrections.
        #Manually correcting words founds, most of the cases I'll catch here,
        #are either, proper words that for some reason made it trough to all
        #filters, and words where the writer have missed some letter.
        #Being the latters the words that I want to correct in this point.
        if not valid_correction:
            if typo not in manual_corrections.keys():
                #Ba answering 1, the possible corrections is discarted.
                #Bu answering 2, the possible correction gets copied to corrections_dict.
                try:
                    answer = int(raw_input("Current word: 1.-{0}  Proposed correction: 2.-{1}".format(typo,possible_correction)))
                except ValueError:
                    answer = int(raw_input("Current word: 1.-{0}  Proposed correction: 2.-{1}".format(typo,possible_correction)))
                    
                if answer == 2:
                    manual_corrections[typo] = possible_correction
                    valid_correction = True
                else:
                    manual_corrections[typo] = ''
            else:
                if manual_corrections[typo] == possible_correction:
                    valid_correction = True
                    
    return valid_correction



def get_places_and_names():
    #Reads the data dump from geonames
    places_words = {}
    f = open('corpora/MX.txt','r')
    for row in f:
        row = row.split('\t')[1]
        for word in row.split(' '):
            word = only_words.sub('',word)
            if word in places_words.keys():
                places_words[word] += 1
            else:
                places_words[word] = 1
    
    return places_words
    
def clean_text(key_k,key_v, corrections = {}):
    u'''
    In spanish we use an ortographic figure called "Accents"
    that are put on top of a vowel and sometimes are used to differentiate
    words that are written the same but are pronuntiated different.
    As the keys of the dict unicode_corrections and the values are considered 
    different characters, I'm replacing all inverse accents with accents, 
    as that's the correct way for writting accents in spanish,
    it's very likely the former appear in the dataset only due to typos.
    '''
    unicode_corrections = {   u'À' : u'Á',
                              u'È' : u'É',
                              u'Ì' : u'Í',
                              u'Ò' : u'Ó',
                              u'Ù' : u'Ú',
                                }
    
    #Some strings contained double spaces, I'm replacing them with one space.                            
    key_v = re.sub(re_double_space,' ', key_v)
    
    
    if isinstance(key_v, unicode):
        for correction in unicode_corrections:    
            key_v = key_v.replace(correction,unicode_corrections[correction])
            key_v = key_v.replace(correction.lower(),unicode_corrections[correction].lower())
    key_v = key_v.split(" ")
    processed = []
    
    for word in key_v:
        check = True
        
        if word.isupper():
            print word
            
        temp = word.replace('.','').lower()
        
        #The exceptions list contains acronyms and abbreviations that
        #I found doing an exploratory analysis of the data, and that I don't
        #want them to be part of this process.
        if temp in check_exceptions_l:
            #print temp
            word = check_exceptions[check_exceptions_l.index(temp)]
            
        if word in check_exceptions:
            #print word
            check = False
        

        if check:                            
    #       I want to capitalize all words that are not exceptions,
            #but if the word starts with any symbot that's not a leter,
            #capitalize() won't work, so I'm deleteing anything that is not
            #a letter and then applying the capitalization.
            temp = only_words.sub('',word)
            word = word.replace(temp,temp.capitalize())    

    #       Replacing common abbreviations with their corresponding full word
            temp = only_words.sub('',word)
            for correct_word in corrections:
                if temp in corrections[correct_word]:
                    #print word
                    word = re.sub(u'(' + temp + u'\.{0,1})', correct_word, word)
                    break

            # Some manual correction
            if word == '!6':
                word = '16'
            
            # There are some cases where at this point I get empty spaces,
            # I don't want those to be part of the final sentence.
            if len(word) == 0:
                continue
            
            
        
        processed.append(word)
    key_v = " ".join(processed)
    
    #There are some scenarios where for some reason ( probably due to
    #the usage of some non ascii characters), the last character sometimes is a space.
    #This is to avoid so.    
    if key_v == '':
        return key_v
    if key_v[-1] == ' ':
        key_v = key_v[:-1]
            
    return key_v  


#def get_words(all_words = {}):
    #Assigning a cofficient, to every word depending on how many times it appears
    #in the dataset.
#    all_words_2 = {}
#    all_words_2["most_common"] = all_words["most_common"]
#    for word in all_words.keys():
#        if word == 'most_common':
#            continue
#        all_words_2[word] = float(1 - math.log10(all_words[word]+1) / math.log10(all_words["most_common"]+1))
#    return all_words_2


def xml_to_dict(filename, insert = False):
    #Reads the xml file process them, and inserts the documents into MongoDB
    #in bulks of 1000, as they are too many to keep them in memory.

    print "Reading XML"
    #Create main iterator:
    context = iter(ET.iterparse(filename))
    _, root = next(context)
    documents_list = []
    words_dict["most_common"] = 0
    #Parsing XML
    for _,element in context:
        
        document = {}
        #if element.tag == 'tag':
        #            
        #    if element.attrib['k'] in tag_texts_dict.keys():
        #        tag_texts_dict[element.attrib['k']].append(element.attrib['v'])
        #    else:
        #        tag_texts_dict[element.attrib['k']] = [element.attrib['v']]  

        
        if element.tag in accepted_tags:
            document["type"] = element.tag
            
            attribs = element.attrib
            for attrib in attribs.keys():
                
                if attrib in CREATED:
                    if "created" not in document.keys():
                         document["created"] = {}
                    document["created"][attrib] = attribs[attrib]
                    continue
                if attrib not in document.keys():
                    document[attrib] = attribs[attrib]
                    
            
            for sub_element in element:
                
                if sub_element.tag == 'nd':
                    if "node_refs" not in document.keys():
                        document["node_refs"] = []    
                    
                    document["node_refs"].append(sub_element.attrib["ref"])
                    
                if sub_element.tag == 'tag':
                    
                    cleaned_text = clean_text(sub_element.attrib['k'], sub_element.attrib['v'], corrections)
                    splitted_tag = split_pattern.split(cleaned_text)
                    for word in splitted_tag:
                        
                        if re.search(r'\d',word):
                            continue
                        
                        #Saves a dictionary of words with punctuation signs
                        #for analysis purposes
                        word_without_punctuation = word.replace('.','')
                        if re_abbrev.search(word):
                            if word_without_punctuation not in words_with_punctuation.keys():
                                words_with_punctuation[word_without_punctuation] = []
                                if word not in words_with_punctuation[word_without_punctuation]:
                                    words_with_punctuation[word_without_punctuation].append(word)
                        word = word_without_punctuation
                        
                        if len(word) == 0:
                            continue
                        
                        # Saving all the words used in the dataset, and how many
                        # times it appears
                        if word in words_dict.keys():
                            words_dict[word] += 1
                            if words_dict[word] > words_dict["most_common"]:
                                words_dict["most_common"] = words_dict[word]
                        else:
                            words_dict[word] = 1
                   
                   
                   #Tag_texts_dicts saves a copy of the texts from every document,
                   #and the id of the document where it appears.
                    if sub_element.attrib['k'] in tag_texts_dict.keys():
                        if cleaned_text in tag_texts_dict[sub_element.attrib['k']].keys():
                            tag_texts_dict[sub_element.attrib['k']][cleaned_text].append(document['id'])
                        else:
                            tag_texts_dict[sub_element.attrib['k']][cleaned_text] = [document['id']]
                    else:
                        tag_texts_dict[sub_element.attrib['k']] = {cleaned_text: [document['id']]} 
                        
                    if "addr:" in sub_element.attrib['k']:
                    
                    
                    #Halt addr:street:
                        if "street:" in sub_element.attrib['k'] or problemchars.search(sub_element.attrib['k']):
                            continue
                        if "address" not in document.keys():
                            document["address"] = {}
                        
                        
                        document["address"][sub_element.attrib['k'].replace("addr:",'')] = sub_element.attrib['v']
                        
                    else:
                        document[sub_element.attrib['k']] = sub_element.attrib['v']                    

                sub_element.clear()
                
            documents_list.append(document)
                
            if len(documents_list) == 1000 and insert:
                zmg_collection.insert(documents_list)
                documents_list = []
            element.clear()        
    root.clear()
        
    if len(documents_list) > 0 and insert:
        zmg_collection.insert(documents_list)
        documents_list = []




def apply_word_corrections(string):
    #Apply spelling corrections found to document tags
    new_string = []
    words = string.split(' ')
    for word in words:
        cleaned_word = only_words.sub('',word)
        if len(cleaned_word) != 0:
            if cleaned_word in corrections_dict.keys():
                word = word.replace(cleaned_word,corrections_dict[cleaned_word])
        
        new_string.append(word)
    if len(new_string) != 0:     
        string = ' '.join(new_string)
    
    return string





#   Main Program    #
print "Initializing..."
#XML file name:
filename = 'map'

#Global Variables
accepted_tags = [ "node","way"]
CREATED = [ "version", "changeset", "timestamp", "user", "uid"]
words_dict = {} #Will be used to find streetnames which might refer to the same place.
#words_with_unicode_chars = {}
words_with_punctuation = {}
tag_texts_dict = {} #Will keep in memory all the texts from tags. 

corrections = { "Avenida"   : ["Av", "Ave"],
                        "Boulevard" : ["Blvd", "Bulevard", "Boulevar", "Bulevar"],
                        "Carretera" : ["Carr", "Carr", "Ctra"],
                        "Calle"     : ["Call", "C"],
                        "Prolongacion" : ["Prol"],
                        "Libramiento"  : ["Libr"],
                        "Francisco" : ["Fco"],
                        "Calzada" : ["Calz"],
                        "Coordinacion" : ["Coord"],
                        "Departamento" : ["Dep"],
                        "Poniente": ["Pte"],
                        "Norte" : ["Nte"],
                        "Oriente" : ["Ote"],
                        "Privada" : ["Priv"],
                        "Santa" : ["Sta"],
                        "Sucursal" : ["Suc"],
                        "San" : ["Sn"],
                        "Unidad Medico Familiar" : ["Umf"],
                        "Secundaria" : ["Sec"],
                        "Tecnica" : ["Tec"],
                        "Numero" : ["No"],
                        "Presbitero" : ["Pbro"],
                        "Profesor" : ["Profr"],
                        "Licenciado" : ["Lic"],
                        "Laboratorio" : ["Lab"],
                        "Instituto" : ["Inst"],
                        "Ingeniero" : ["Ing"],
                        "General" : ["Gral"],
                        "Febrero" : ["Feb"],
                        "Escuela" : ["Esc"],
                        "Escuela Secundaria Tecnica" : ["Est"],
                        "Doctor" : ["Dr"],
                        "Departamento" : ["Dpto", "Dep"],
                        "Comercial" : ["Comercal"],
                        "1o" : ["1ro"],
                        "Arquitecto" : ["Arq"],
                        "Federal" : ["Fed"],
                        "Division" : ["Div"],
                        "U. de G." : ["Udeg", "Udg"]
                        }

check_exceptions =["W.C.", "V.", "E.E.", "U.U.", "T.R.", "T.", "St.", 
                   "S.J.", "S.A.", "C.V.", "R.L.", "S.", "R.", "Z.", 
                   "I.T.E.S.O.", "L.", "P.", "N.", "Ma.", "M.",
                   "L.C.P.", "B.", "Jr.", "J.", "I.", "H.", "G.", "F.",
                   "C.F.E.", "C.", "A.A.", "A.C.", "DECO.", "C.P.A.", "J.A.",
                   "ART", "CUAAD", "DIS", "II", "A.M.", "P.M.", "I.S.S.S.T.E",
                   "I.M.S.S.", "C.U.C.E.I.", "C.U.C.B.A.", "C.U.C.S.", "C.U.C.E.A.", "S.E.P."]

check_exceptions_l = map(lambda x: x.replace('.','').lower(),check_exceptions)


#Regular Expressions

problemchars = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')
split_pattern = re.compile(u'[^A-Za-z0-9.!ÑñÁáÉéÍíÓóÚú]+')
only_words = re.compile(u'[^A-Za-zÑñÁáÉéÍíÓóÚú]+')
re_double_space = re.compile(r'[^\S\r\n]{2,}')
re_abbrev = re.compile(r'^([A-Za-zÑñÁáÉéÍíÓóÚú])+\.$')
special_char = re.compile(u'[ÑñÁáÉéÍíÓóÚú]')

#Initializing connection to MongoDB
client = MongoClient("mongodb://localhost:27017")
db = client.osm

#ZMG stands for "Zona Metropolitana de Guadalajara".
zmg_collection = db.osm_zmg
read_from_db = True



words_abc_size = {} #Words_dict sorted by size and first letter.
possible_typos = {} #Collects possible typos detected by edit_distance().
possible_typos_list = [] #A list of all words detected as possible typos.
typos_prob = {} #Possible typos and how many times appears in the dataset
typos_dict = {}
corrections_dict = {}
 
corrections_from_atd_file = 'corrections_from_atd.pkl'
consulted_file = 'atd_consulted.pkl'
typos_file = 'atd_typos.pkl'
manual_corrections_file = 'manual_corrections.pkl'
    
corrections_from_atd = open_file(corrections_from_atd_file,{})
consulted = open_file(consulted_file, [])
typos = open_file(typos_file,[])
manual_corrections = open_file(manual_corrections_file, {}) 


#Read XML to a List of Dictionaries.
xml_to_dict(filename)
#Process words and detect typos
words_process()
#Save changes to db.
save_changes()        



