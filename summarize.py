#!/usr/bin/env python
import itertools
import nltk
from nltk.corpus import stopwords
import string
import os
import re

DEFAULT_UNICODE_ENCODING = "windows-1252"

stop_words = stopwords.words('english')

LOWER_BOUND = .20 #The low end of shared words to consider
UPPER_BOUND = .90 #The high end, since anything above this is probably SEO garbage or a duplicate sentence

def is_unimportant(word):
    """Decides if a word is ok to toss out for the sentence comparisons"""
    return word in ['.', '!', ',', ] or '\'' in word or word in stop_words

def only_important(sent):
    """Just a little wrapper to filter on is_unimportant"""
    return filter(lambda w: not is_unimportant(w), sent)

def compare_sents(sent1, sent2):
    """Compare two word-tokenized sentences for shared words"""
    if not len(sent1) or not len(sent2):
        return 0
    return len(set(only_important(sent1)) & set(only_important(sent2))) / ((len(sent1) + len(sent2)) / 2.0)

def compare_sents_bounded(sent1, sent2):
    """If the result of compare_sents is not between LOWER_BOUND and
    UPPER_BOUND, it returns 0 instead, so outliers don't mess with the sum"""
    cmpd = compare_sents(sent1, sent2)
    if cmpd <= LOWER_BOUND or cmpd >= UPPER_BOUND:
        return 0
    return cmpd

def compute_score(sent, sents):
    """Computes the average score of sent vs the other sentences (the result of
    sent vs itself isn't counted because it's 1, and that's above
    UPPER_BOUND)"""
    if not len(sent):
        return 0
    return sum( compare_sents_bounded(sent, sent1) for sent1 in sents ) / float(len(sents))

def summarize_block(block):
    """Return the sentence that best summarizes block"""
    sents = nltk.sent_tokenize(block)
    word_sents = map(nltk.word_tokenize, sents)
    d = dict( (compute_score(word_sent, word_sents), sent) for sent, word_sent in zip(sents, word_sents) )
    return d[max(d.keys())]

def find_likely_body(b):
    """Find the tag with the most directly-descended <p> tags"""
    return max(b.find_all(), key=lambda t: len(t.find_all('p', recursive=False)))

class Summary(object):
    def __init__(self, url, article_html, title, summaries):
        self.url = url
        self.article_html = article_html
        self.title = title
        self.summaries = summaries

    def __repr__(self):
        return 'Summary({0}, {1}, {2}, {3}, {4})'.format(
            repr(self.url), repr(self.article_html), repr(self.title), repr(summaries)
        )

    def __str__(self):
        # Make sure we convert unconvertable unicode to ascii
        summaries = []
        for i in range(0, len(self.summaries)):
            try:
                sumdec = self.summaries[i].decode(DEFAULT_UNICODE_ENCODING)
                s = sumdec.encode('ascii', 'ignore')
                summaries.append(s)
            except Exception as e:
                print("Caught exception converting summary %s to ascii: %s" % (self.summaries[i], e, ))
        #summaries = [ s.encode('ascii', 'ignore') for s in self.summaries ]
        return "{0} - {1}\n\n{2}".format(self.title, self.url, '\n'.join(summaries))

def summarize_text(text):
    # Here I assume paragraphs are delimited by blank lines
    # I am also assuming that lines are ended with a new line.
    paras = []
    para = []
    for line in text.split("\n"):
        line = line.strip()
        if len(line) == 0:
            if len(para) > 0:
                paras.append(re.sub('\s+', ' ', ' '.join(para)))
                para = []
        else:
            para.append(line)
    if len(para) > 0:
        paras.append(re.sub('\s+', ' ', ' '.join(para)))

    summaries = [ summarize_block(p) for p in paras ]
    return Summary(None, text, None, summaries)

def summarize_html(html, url = None):
    import bs4
    from tidylib import tidy_document
    html, errors = tidy_document(html, options={'numeric-entities':1})
    html = bs4.BeautifulSoup(html)
    b = find_likely_body(html)
    summaries = map(lambda p: re.sub('\s+', ' ', summarize_block(p.text)).strip(), b.find_all('p'))
    summaries = sorted(set(summaries), key=summaries.index) #dedpulicate and preserve order
    summaries = [ re.sub('\s+', ' ', summary.strip()) for summary in summaries if filter(lambda c: c.lower() in string.letters, summary) ]
    return Summary(url, b, html.title.text if html.title else None, summaries)

def summarize_url(url):
    import requests

    html = requests.get(url).text
    return summarize_html(html, url)

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: %s <http://site/article.html or filename.txt>" % (sys.argv[0], ))
        exit(0)

    filename_or_url = sys.argv[1]

    if filename_or_url.startswith('http'):
        print summarize_url(filename_or_url)
    elif os.path.isfile(filename_or_url):
        with open(filename_or_url, 'r') as f:
            print summarize_text(f.read())
    else:
        print("%s must be a file or web url" % (filename_or_url, ))

