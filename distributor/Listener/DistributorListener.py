import numpy as np
from pandas import DataFrame as df
import pandas as pd
import os
import shutil
from robot.running import Keyword

class DistributorListener:
    ROBOT_LISTENER_API_VERSION = 3

    def __init__(self, nodes=100, outputpath="distributor_output/"):
        # create a new dataframe with columns suite (string) and test (string) and datadriver (boolean)

        self.tests = df(columns=["suite", "test", "datadriver"])
        # convert type of column datadriver to boolean
        self.tests["datadriver"] = self.tests["datadriver"].astype(bool)
        self.outputpath = outputpath
        # Create a new directory for the output files
        # If the directory already exists, delete it and create a new one
        if os.path.exists(self.outputpath):
            shutil.rmtree(self.outputpath)
        os.mkdir(self.outputpath)
        self.nodes = nodes
        self.uses_datadriver = False
        print("Distributor initialized")

    def start_suite(self, suite, result):
        if any(item.name == "DataDriver" for item in suite.resource.imports):
            self.uses_datadriver = True
        else:
            self.uses_datadriver = False
        if suite.has_setup:
            suite.setup = Keyword('No Operation')
        if suite.has_teardown:
            suite.teardown = Keyword('No Operation')
        # Remove all items from suite.resource.imports if the name of the item is not DataDriver
        suite.resource.imports = [
            item for item in suite.resource.imports if item.name == "DataDriver"
        ]

    def start_test(self, test, result):
        # Replace all keywords with the keyword No Operation
        # This is done to avoid the execution of the test
        if test.has_setup:
            test.setup = Keyword('No Operation')
        if test.has_teardown:
            test.teardown = Keyword('No Operation')
        test.body = [Keyword('No Operation')]

    def end_suite(self, suite, result):
        # If suite contains tests, append them to the list of dictionaries with suite name and testname
        if len(suite.tests) > 0:
            for test in suite.tests:
                self.tests = pd.concat(
                    [
                        self.tests,
                        pd.DataFrame(
                            [[suite.longname, test.name, self.uses_datadriver]],
                            columns=["suite", "test", "datadriver"],
                        ),
                    ],
                    ignore_index=True,
                )

    def close(self):
        """
        Split the self.tests into n number of chunks (where n is self.nodes)
        and create at least one chunk for each suite
        and try to create chunks of similar size

        Each chunk is a list of dictionaries with suite name and testname

        Example 1:
        1. If there are 3 suites with
        suite 1: 2 tests
        suite 2: 6 tests
        suite 3: 8 tests

        and self.nodes = 4

        then the chunks will be:
        chunk 1:
        suite: suite 1, test: test 1
        suite: suite 1, test: test 2
        suite: suite 2, test: test 5
        suite: suite 2, test: test 6
        chunk 2:
        suite: suite 2, test: test 1
        suite: suite 2, test: test 2
        suite: suite 2, test: test 3
        suite: suite 2, test: test 4
        chunk 3:
        suite: suite 3, test: test 1
        suite: suite 3, test: test 2
        suite: suite 3, test: test 3
        suite: suite 3, test: test 4
        chunk 4:
        suite: suite 3, test: test 5
        suite: suite 3, test: test 6
        suite: suite 3, test: test 7
        suite: suite 3, test: test 8


        Example 2:
        1. If there are 2 suites with
        suite 1: 6 tests
        suite 2: 2 tests
        and self.nodes = 4

        then the chunks will be:
        chunk 1:
        suite: suite 1, test: test 1
        suite: suite 1, test: test 2
        chunk 2:
        suite: suite 1, test: test 3
        suite: suite 1, test: test 4
        chunk 3:
        suite: suite 1, test: test 5
        suite: suite 1, test: test 6
        chunk 4:
        suite: suite 2, test: test 1
        suite: suite 2, test: test 2
        """
        # group the self.tests per suite
        grouped_tests = self.tests.groupby("suite")
        # calculate percentage for each group of tests
        grouped_tests_percentage = grouped_tests.size() / len(self.tests)
        # calculate number of nodes for each group of tests (where n is self.nodes) rounded, but at least 1
        grouped_tests_nodes = grouped_tests_percentage * self.nodes
        grouped_tests_nodes = grouped_tests_nodes.apply(lambda x: max(1, round(x)))
        print(grouped_tests_nodes)
        # create n chunks for each group of tests, where n is the grouped_tests_nodes for that group
        grouped_tests_chunks = grouped_tests.apply(
            lambda x: np.array_split(x, grouped_tests_nodes[x.name])
        )
        # print the number of chunks for each group of tests
        # print the number of tests in each chunk for each group of tests
        for suite, chunks in grouped_tests_chunks.items():
            print(suite)
            chunk_number = 0
            for chunk in chunks:
                print(len(chunk))
                print(chunk.to_dict("records"))
                # Generate incremental number for each chunk
                # Create a new .json file with the incremental number
                # Write the chunk to the file
                chunk_number += 1
                filename = "distributor_" + suite.replace(" ", "_") + "_" + "{:03d}".format(chunk_number) + ".json"
                chunk.to_json(self.outputpath + filename, orient="records")

