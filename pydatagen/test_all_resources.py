#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2022 Confluent Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Script to dry-run all avro schemas as defined under folder resources/
# Test parameters as defined under class Args(BaseModel)

import os

from pydantic import BaseModel

from pydatagen import main


class Args(BaseModel):
    schema_filename: str
    dry_run: bool = True
    headers_filename: str = "dynamic_000.py"
    keyfield: str = None
    key_json: bool = False
    interval: int = 10
    iterations: int = 10


if __name__ == "__main__":
    schema_files = sorted(os.listdir("resources"))
    qty_files = len(schema_files)
    for n, file in enumerate(schema_files):
        print(f"\n\nSchema file #{n+1}/{qty_files}: {file}\n")
        args = Args(schema_filename=file)
        main(args)
