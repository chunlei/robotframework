#  Copyright 2008-2015 Nokia Networks
#  Copyright 2016-     Robot Framework Foundation
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import os

from .lexer import Token, get_tokens, get_resource_tokens
from .model import (File, SettingSection, VariableSection, TestCaseSection,
                    KeywordSection, CommentSection, TestCase, Keyword, ForLoop,
                    get_statements)


def get_model(source, data_only=False, curdir=None):
    tokens = get_tokens(source, data_only)
    return _build_model(get_statements(tokens, curdir))


def get_resource_model(source, data_only=False, curdir=None):
    tokens = get_resource_tokens(source, data_only)
    return _build_model(get_statements(tokens, curdir))


def _build_model(statements):
    builder = FileBuilder()
    stack = [builder]
    for statement in statements:
        while not stack[-1].handles(statement):
            stack.pop()
        builder = stack[-1].statement(statement)
        if builder:
            stack.append(builder)
    return stack[0].model


class Builder(object):

    def __init__(self, model):
        self.model = model

    def handles(self, statement):
        return True

    def statement(self, statement):
        raise NotImplementedError


class FileBuilder(Builder):

    def __init__(self, model=None):
        Builder.__init__(self, model or File())

    def statement(self, statement):
        try:
            section_class, builder_class = {
                Token.SETTING_HEADER: (SettingSection, SectionBuilder),
                Token.VARIABLE_HEADER: (VariableSection, SectionBuilder),
                Token.TESTCASE_HEADER: (TestCaseSection, TestCaseSectionBuilder),
                Token.KEYWORD_HEADER: (KeywordSection, KeywordSectionBuilder),
                Token.COMMENT_HEADER: (CommentSection, SectionBuilder)
            }[statement.type]
            section = section_class(statement)
        except KeyError:
            section = CommentSection(body=[statement])
            builder_class = SectionBuilder
        self.model.sections.append(section)
        return builder_class(section)


class SectionBuilder(Builder):

    def handles(self, statement):
        return statement.type not in Token.HEADER_TOKENS

    def statement(self, statement):
        self.model.body.add(statement)


class TestCaseSectionBuilder(SectionBuilder):

    def statement(self, statement):
        if statement.type == Token.EOL:
            return self
        model = TestCase(statement)
        self.model.body.add(model)
        return TestOrKeywordBuilder(model)


class KeywordSectionBuilder(SectionBuilder):

    def statement(self, statement):
        if statement.type == Token.EOL:
            return self
        model = Keyword(statement)
        self.model.body.add(model)
        return TestOrKeywordBuilder(model)


class TestOrKeywordBuilder(Builder):

    def handles(self, statement):
        return statement.type not in Token.HEADER_TOKENS + (Token.NAME,)

    def statement(self, statement):
        if statement.type == Token.FOR:
            model = ForLoop(statement)
            self.model.body.add(model)
            return ForLoopBuilder(model)
        else:
            self.model.body.add(statement)


class ForLoopBuilder(Builder):

    def __init__(self, model):
        Builder.__init__(self, model)
        self._end = False

    def handles(self, statement):
        return not self._end and statement.type != Token.NAME

    def statement(self, statement):
        if statement.type == Token.END:
            self.model.end = statement
            self._end = True
        else:
            self.model.body.add(statement)
