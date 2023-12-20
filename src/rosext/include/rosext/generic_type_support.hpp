// MIT License
// 
// Copyright (c) 2021, ETRI. 
// 
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
// 
// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.
// 
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.

// rosext.generic_type_support (rosext)
// created by: paraby@gmail.com

#ifndef ROSEXT__GENERIC_TYPE_SUPPORT_HPP_
#define ROSEXT__GENERIC_TYPE_SUPPORT_HPP_
#include <memory>
#include <string>
#include <tuple>

#include "rcpputils/shared_library.hpp"
#include "rosidl_runtime_cpp/message_type_support_decl.hpp"
#include "rclcpp/visibility_control.hpp"
namespace rosext
{
  /*
    RCLCPP_PUBLIC
    std::shared_ptr<rcpputils::SharedLibrary>
    get_typesupport_library(const std::string & type, const std::string & typesupport_identifier);
    */

    RCLCPP_PUBLIC
    const rosidl_message_type_support_t *
    get_generic_typesupport_handle(
        const std::string & type,
        const std::string & typesupport_identifier); 
//        rcpputils::SharedLibrary & library);
}
#endif // ROSEXT__GENERIC_TYPE_SUPPORT_HPP_
