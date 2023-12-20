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

// Author: parasby@gmail.com

#include <memory>
#include <string>
#include <map>
#include <stdexcept>
#include <tuple>

#include "rosext/generic_type_support.hpp"


#include "rcl/subscription.h"

#include "rclcpp/exceptions.hpp"
#include "rosidl_runtime_cpp/message_type_support_decl.hpp"
#include "rosidl_typesupport_cpp/identifier.hpp"
#include "rosidl_typesupport_c/type_support_map.h"


#include "rosidl_typesupport_fastrtps_cpp/identifier.hpp"
#include "rosidl_typesupport_fastrtps_cpp/message_type_support.h"
#include "rosidl_typesupport_fastrtps_cpp/message_type_support_decl.hpp"

#define MAX_TYPE_SUPPORT_SIZE 1000
namespace rosext
{
    

std::tuple<std::string, std::string>
extract_namespace_and_type(const std::string &full_type)
{
    char type_separator = '/';

    auto found= full_type.find_last_of(type_separator);

    if (found == std::string::npos || 
        found == 0 || 
        found == full_type.length() -1)
    {
        throw std::runtime_error(
            "Message type is not of the form package/type and cannot be processed");
    }

    std::string t_namespace = full_type.substr(0, found);
    std::string t_name = full_type.substr(found+1);

    found = t_namespace.find_first_of(type_separator);

    if (found != std::string::npos && 
        found != 0 &&
        found != t_namespace.length() -1)
    {
        t_namespace.replace(found,1,"::");
    }
    
    return std::make_tuple(t_namespace, t_name);
}




bool _generic_cdr_serialize(
    const void *untyped_ros_message,
    eprosima::fastcdr::Cdr &cdr)
{
     throw std::runtime_error(
          "cdr_serialized called");
    return 0;
}

bool _generic_cdr_deserialize(         
    eprosima::fastcdr::Cdr &cdr, 
    void *untyped_ros_message)
{
    throw std::runtime_error(
          "_generic_cdr_deserialize called");
    return 0;
} 

uint32_t _generic_get_serializeed_size(
    const void *untyped_ros_message)
{
    throw std::runtime_error(
          "_generic_get_serializeed_size called");
    return 0;    
}

size_t _generic_max_serializeed_size(
    bool &full_bounded)
{
    /*
    throw std::runtime_error(
          "_generic_max_serializeed_size called");
          */
    
    //std::cerr<<"called: _generic_max_serializeed_size" <<std::endl;

    return 0;
}



const rosidl_message_type_support_t *get_generic_message_typesupport_handle_function(
    const rosidl_message_type_support_t * handle, const char * identifier) noexcept
{
    /*throw std::runtime_error(
          "get_generic_message_typesupport_handle_function called for " +std::string(identifier));
          */
    // std::cerr<<"called: get_generic_message_typesupport_handle_function" <<std::endl;
    return handle;
}    

// fastrtps only callbacks
static message_type_support_callbacks_t __generic_callbacks = {
    "my_pkg::msg",
    "ThreeNum",
    _generic_cdr_serialize,
    _generic_cdr_deserialize,
    _generic_get_serializeed_size,
    _generic_max_serializeed_size
};

static rosidl_message_type_support_t _generic_handle = {
    rosidl_typesupport_fastrtps_cpp::typesupport_identifier,
    &__generic_callbacks, 
    get_generic_message_typesupport_handle_function
};

// key = typename, rosidl_message_type_support_t..
static std::map<std::string, message_type_support_callbacks_t>  __generic_type_callback_helpers;
static std::map<std::string, rosidl_message_type_support_t>  __generic_type_helpers;
static std::map<std::string, std::tuple<std::string, std::string>> __type_name_helpers;

const rosidl_message_type_support_t *
get_generic_typesupport_handle(  
    const std::string & type,
    const std::string & typesupport_identifier)
{

    //  여기에서는 type으로 찾는다. type에 대한 mapping이 들어있는 것으로 설정
    //return rosext::__generic_type_helpers[std::string(typesupport_identifier)];
    auto itr = __generic_type_helpers.find(type);
    if (itr == __generic_type_helpers.end())
    {
        if ( __generic_type_helpers.size() >=MAX_TYPE_SUPPORT_SIZE-1)
        {
            throw std::runtime_error(
                "Two many types are supported for raw pub/sub");
        }
        //__generic_type_helpers.insert(type, { })
        std::string t_namespace;
        std::string t_name;
        std::tie(t_namespace, t_name) = extract_namespace_and_type(type);

        auto strret = __type_name_helpers.insert( {type, {t_namespace, t_name}});

        // message_type_support_callbacks_t의 namesapce 부분이 char *라서 문제가 발생
        // 위에서 t_namesapce,t_name이 scope를 벗어나며 삭제되기 깨문에, t_namespace.c_str()도 삭제됨.

        message_type_support_callbacks_t tmp = {
            std::get<0>(strret.first->second).c_str(), // t_namesapce
             std::get<1>(strret.first->second).c_str(), // t_name
                _generic_cdr_serialize,
                _generic_cdr_deserialize,
                _generic_get_serializeed_size,
                _generic_max_serializeed_size
        };
        auto ret = __generic_type_callback_helpers.insert( {type, tmp} );

        auto finder = __generic_type_callback_helpers.find(type);

        if (finder == __generic_type_callback_helpers.end())
        {
             throw std::runtime_error(
                "Some error found");
        }
               
        rosidl_message_type_support_t mtst_tmp = {
            rosidl_typesupport_fastrtps_cpp::typesupport_identifier,
            //const_cast<message_type_support_callbacks_t *>( &(ret.first->second)), 
            & finder->second,
            get_generic_message_typesupport_handle_function
        };

        auto tret = __generic_type_helpers.insert( {type,mtst_tmp});    

        message_type_support_callbacks_t *pp = (message_type_support_callbacks_t *)tret.first->second.data;
        //std::cerr << "Type regist" << pp->message_name_ << ":" << pp->message_namespace_ << std::endl;

        return &(tret.first->second);       
    }
    else
    {
        message_type_support_callbacks_t *pp = (message_type_support_callbacks_t *)itr->second.data;

        //std::cerr << "Type found" << pp->message_name_ << ":" << pp->message_namespace_ << std::endl;        

        return const_cast<rosidl_message_type_support_t *>(&itr->second);     
    }
} 
} // namespace rosext        