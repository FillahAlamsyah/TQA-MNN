#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
Created on Mar 2, 2017

.. codeauthor: svitlana vakulenko
    <svitlana.vakulenko@gmail.com>

'''
import unittest

import os
import sys
import pandas as pd
import numpy as np
import re
import random


PATH = './data/'
SAMPLE_TABLE = 'OOE_Wanderungen_Zeitreihe.csv'
TABLE_DATA = './data/table_data.txt'
SIM_DATA = './data/sim_data.txt'

QUESTION_TEMPLATE = 'What is the {} for {}?\t{}\t{}'
# QUESTION_TEMPLATE = 'What is the {} in {}?\t{}\t{}'

def tokenize(sent):
    '''Return the tokens of a sentence including punctuation.

    >>> tokenize('Bob dropped the apple. Where is the apple?')
    ['Bob', 'dropped', 'the', 'apple', '.', 'Where', 'is', 'the', 'apple', '?']
    '''
    return [x.strip() for x in re.split('(\W+)?', sent) if x.strip()]


def parse_tables(lines, only_supporting=False):
    '''Parse stories provided in the bAbi tasks format

    If only_supporting is true, only the sentences that support the answer are kept.
    '''
    data = []
    story = []
    for line in lines:
        try:
            line = line.decode('utf-8').strip()
            nid, line = line.split(' ', 1)
            nid = int(nid)
            if nid == 1:
                story = []
            if '\t' in line:
                q, a, supporting = line.split('\t')
                q = tokenize(q)
                substory = None
                if only_supporting:
                    # Only select the related substory
                    supporting = map(int, supporting.split())
                    substory = [story[i - 1] for i in supporting]
                else:
                    # Provide all the substories
                    substory = [x for x in story if x]
                data.append((substory, q, a))
                story.append('')
            else:
                sent = tokenize(line)
                story.append(sent)
        except:
            e = sys.exc_info()[0]
            print(e)
    return data


def get_tables(path, only_supporting=False, max_length=None):
    '''Given a file name, read the file, retrieve the stories, and then convert the sentences into a single story.

    If max_length is supplied, any stories longer than max_length tokens will be discarded.
    '''
    with open(path) as f:
        data = parse_tables(f.readlines(), only_supporting=only_supporting)
        # print(data)
        flatten = lambda data: reduce(lambda x, y: x + y, data)
        data = [(flatten(story), q, answer) for story, q, answer in data if not max_length or len(flatten(story)) < max_length]
        return data


def read_tables(fps, delimiter, shuffle=False, limit=False):
    '''
    Input:
    fps <list of strings>  full paths to files to read tables from

    Output:
    tables <dict> {file_path: rows_generator}
    '''
    tables = {}
    for path in fps:
        df = pd.read_csv(path, sep=delimiter)
        if shuffle:
            df_shuffled = df.iloc[np.random.permutation(len(df))]
            df_shuffled.reset_index(drop=True)
            df = df_shuffled
        if limit:
            df = df[:limit]
        tables[path] = df
    return tables


def collect_tables(files):
    # collect file paths
    fps = []
    for file in files:
        fps.append(os.path.join(PATH, file))
    print(fps)
    return read_tables(fps, delimiter=';')


def profile_table(table, n_samples=10):
    columns = table.columns
    print(len(table), 'rows')
    print(len(columns), 'columns')
    print('Header:', columns.values)
    # value distributions across columns
    distribution = [len(set(table[c])) for c in table]
    print('Number of unique values:', distribution)
    print('Mean:', np.mean(distribution))
    sample_values = [list(set(table[c]))[:n_samples] for c in table]
    print('Samples of unique values:', sample_values)
    return sample_values
    types = [type(list(set(table[c]))[0]) for c in table]
    print('Column types:', types)
    # print [len(set(c)) for c in columns]


def get_cat_columns(table):
    '''
    Finds the columns with distinct categorical values to use for question generation
    '''
    # value distributions across columns
    distribution = [len(set(table[c])) for c in table]
    string_columns = [idx for idx, c in enumerate(table) if isinstance(list(set(table[c]))[0], str)]
    # categorical fields
    print ('String columns:', string_columns)
    # exclude non-discriminative columns
    return [idx for idx in string_columns if distribution[idx] > 1]


class TableParser():
    '''
    size <int> regulates the size of the table chunks between QAs
    '''

    def __init__(self, size=2):
        '''
        size <int> of the generated table, i.e. the number of rows
        '''
        self.size = size
        self.count = 0
        self.qs = []
        self.qas = 0

    def simulate_data(self, table, out_path=SIM_DATA, n_tables = 500):
        '''
        Simulate as much data as needed for training. But test on the real table data!
        Generate a synthethic table for training neural network based on a real table statistics
        to increase the number of samples and decrease variance in the columns' domains.
        '''
        with open(out_path, 'w') as self.out_file:
            self.columns = table.columns.values
            sample_values = profile_table(table)
            cat_columns = get_cat_columns(table)
            print (cat_columns)
            self.rows = []
            # generate N_SAMPLES random training data samples
            while self.qas < n_tables:
                self.count += 1
                data_string = str(self.count) + ' '
                values = []
                row = [self.count]
                for idx in xrange(len(self.columns)):
                    # TODO pick sample value at random
                    value = random.choice(sample_values[idx])
                    row.append(value)
                    if isinstance(value, str):
                        values.append(self.columns[idx] + ' : ' + value)
                    else:
                        values.append(self.columns[idx] + ' : ' + str(value))
                data_string += ', '.join(values) + ' .\n'
                self.out_file.write(data_string)
                self.rows.append(row)
                # write random qa after every 2nd sample
                if self.count % self.size == 0:
                    # generate qa 
                    self.generate_qa(cat_columns[0])

    def generate_data(self, table, out_path=TABLE_DATA):
        with open(out_path, 'w') as self.out_file:
            self.columns = table.columns.values
            cat_columns = get_cat_columns(table)
            print (cat_columns)
            self.rows = []
            for row in table.itertuples():
                self.count += 1
                # data_string = str(row[0]+1) + ' '
                data_string = str(self.count) + ' '
                # print row
                values = []
                for idx, value in enumerate(row[1:]):
                    if isinstance(value, str):
                        values.append(self.columns[idx] + ' : ' + value.encode('utf-8'))
                    else:
                        values.append(self.columns[idx] + ' : ' + str(value))
                data_string += ', '.join(values) + ' .\n'
                self.out_file.write(data_string)
                self.rows.append(row)
                # write random qa after every 2nd sample
                if self.count % self.size == 0:
                    # generate qa 
                    self.generate_qa(cat_columns[0])

    def generate_qa(self, cat):
        # print row
        # pick row at random
        s = random.randrange(0, len(self.rows))
        # make sure the values are different for the q field across columns
        # print columns
        q = random.randrange(1, len(self.columns))
        # skip
        if q == cat:
            return
        # print self.rows
        q_string = QUESTION_TEMPLATE.format(self.columns[q], self.rows[s][cat+1],
                                            self.rows[s][q+1],  s+1)
        self.count += 1
        self.out_file.write(str(self.count) + ' ' + q_string + '\n')
        self.qas += 1
        # reset table
        self.count = 0
        self.rows = []

        # print columns[q], row[q]


def test_format_table():
    tables = collect_tables([SAMPLE_TABLE])
    for path, table in tables.items():
        print (path)
        tp = TableParser()
        tp.generate_data(table)


def test_simulate_table():
    tables = collect_tables([SAMPLE_TABLE])
    for path, table in tables.items():
        print (path)
        tp = TableParser()
        tp.simulate_data(table)


class TestTableParser(unittest.TestCase):
    def test_collect_tables(self):
        tables = collect_tables([SAMPLE_TABLE])
        for path, table in tables.items():
            print (path)
            print (table.columns.values)

    def test_profile_table(self):
        tables = collect_tables([SAMPLE_TABLE])
        for path, table in tables.items():
            print (path)
            profile_table(table)


if __name__ == '__main__':
    # unittest.main()
    # test_format_table()
    test_simulate_table()
