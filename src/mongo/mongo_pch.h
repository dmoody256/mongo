/**
 *    Copyright (C) 2019-present MongoDB, Inc.
 *
 *    This program is free software: you can redistribute it and/or modify
 *    it under the terms of the Server Side Public License, version 1,
 *    as published by MongoDB, Inc.
 *
 *    This program is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *    Server Side Public License for more details.
 *
 *    You should have received a copy of the Server Side Public License
 *    along with this program. If not, see
 *    <http://www.mongodb.com/licensing/server-side-public-license>.
 *
 *    As a special exception, the copyright holders give permission to link the
 *    code of portions of this program with the OpenSSL library under certain
 *    conditions as described in each individual source file and distribute
 *    linked combinations including the program with the OpenSSL library. You
 *    must comply with the Server Side Public License in all respects for
 *    all of the code used other than as permitted herein. If you modify file(s)
 *    with this exception, you may extend this exception to your version of the
 *    file(s), but you are not obligated to do so. If you do not wish to do so,
 *    delete this exception statement from your version. If you delete this
 *    exception statement from all source files in the program, then also delete
 *    it in the license file.
 */

#ifndef MONGO_PCH_HEADER
#define MONGO_PCH_HEADER

// This PCH is scoped to all files under src/mongo unless overriden by
// a subdirectory. Only header files that are applicable to all
// mongodb authored C++ should be included here.

// Pull in our parent PCH
#include "../pch.h"

// This PCH will get included in things that are logically C, where we
// don't want to include the C++ headers.
#if defined(__cplusplus)

#include <mongo/platform/basic.h>

#include <boost/optional.hpp>

#include <mongo/config.h>

#include <mongo/base/error_codes.h>
#include <mongo/base/status.h>
#include <mongo/bson/bsonobj.h>
#include <mongo/bson/bsonobjbuilder.h>
#include <mongo/stdx/new.h>
#include <mongo/stdx/unordered_map.h>

#include <mongo/util/str.h>
#include <mongo/util/assert_util.h>
#include <mongo/db/jsobj.h>
#include <mongo/db/client.h>

#endif
#endif
