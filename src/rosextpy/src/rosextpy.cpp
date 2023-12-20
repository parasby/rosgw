// MIT License
// 
// Copyright (c) 2021, Electronics and Telecommunications Research Institute (ETRI) All Rights Reserved.
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

// rosextpy.cpp (rosextpy)
// Author: paraby@gmail.com

#include <pybind11/pybind11.h>


#include "rosext/extnode.hpp"

#define STRINGIFY(x) #x
#define MACRO_STRINGIFY(x) STRINGIFY(x)


namespace py = pybind11;

using namespace rosext;
using namespace rclcpp;

namespace rosextpy {
// When it makes a python extension , it needs caster class.

// class check_init {
//     public:
//     check_init()
//     {        
//         if (!rclcpp::ok())
//         {
//             throw std::runtime_error("rosextpy.init() has not beed called");
//         }
//     }

//     virtual ~check_init() {}
// };

// class Node {   
// public:
//     Node(const std::string &name) : _node(name)
//     {        
//     }

//     Node(const std::string &name, const std::string &namespace_ ) : _node(name, namespace_)
//     {        
        
//     }

//     virtual ~Node(){        
//     }

//     inline const std::string getName()
//     {
//         return _node.get_name();
//     }

//     py::capsule create_generic_subscription(const std::string &topic_name, 
//             const std::string &topic_type, 
//             std::function<void(std::shared_ptr<rclcpp::SerializedMessage>)> callback )
//     {
//         py::capsule obj;

//         return obj;

//     }
    

// //  asdas sub_ = this->create_generic_subscription(topic_name, topic_type, qos , callback);
// //     asdasda pub_ = this->create_generic_publisher(pub_topic_name, topic_type, qos);



// private:
//     check_init _init; 
//     // _init has to be first order. 
//     ExtNode _node;
// };

// void init(py::args args)
// {
//   std::vector<const char *> arg_c_values(args.size());
//   for (size_t i = 0; i < args.size(); ++i) {
//     // CPython owns const char * memory - no need to free it
//     arg_c_values[i] = PyUnicode_AsUTF8(args[i].ptr());
//     if (!arg_c_values[i]) {
//       throw py::error_already_set();
//     }
//   }

//   int argc = static_cast<int>(arg_c_values.size());
//   const char ** argv = argc > 0 ? &(arg_c_values[0]) : nullptr;

// //  For Debug
// //   for (int i=0; i < argc; i++)
// //   {
// //       std::cerr <<"Argv["<<i<<"]="<<argv[i]<<std::endl;
// //   }

//   rclcpp::init(argc,argv);
// }




//  RCLCPP_PUBLIC
//     const rosidl_message_type_support_t *
//     get_generic_typesupport_handle(
//         const std::string & type,
//         const std::string & typesupport_identifier); 

// py::object get_serialized_type(const std::string &typename)
// {
//     rosidl_message_type_support_t *tss = 
//         get_generic_typesupport_handle(typename,"rosidl_typesupport_cpp");

//     return types..     
// }

static void *create_ros_message_serialized_msg(void)
{
    std::cerr<<"don't be called here[create_ros_message_serialized_msg]" <<std::endl;
    std::cerr << "Please Call publish with raw message"<<std::endl;
    return nullptr;   
}

bool convert_from_py_serialized_msg(PyObject *_pymsg, void * _ros_message)
{
    std::cerr<<"don't be called here[convert_from_py_serialized_msg]" <<std::endl;
    std::cerr << "Please Call publish with raw message"<<std::endl;
    return true;
}

PyObject *convert_to_py_serialized_msg(void * _raw_ros_message)
{
    std::cerr<<"don't be called here[convert_to_py_serialized_msg]" <<std::endl;
    std::cerr << "Please Call take_message(..., raw=True)"<<std::endl;
    
    return nullptr;
}

void destroy_ros_message_serialized_msg(void * _raw_ros_message)
{
    std::cerr<<"don't be called here[destroy_ros_message_serialized_msg]" <<std::endl;    
}

void *get_type_support(const std::string &clsname)
{
    return (void *)get_generic_typesupport_handle(clsname,"rosidl_typesupport_cpp");
}


} // namespace rosextpy

// int add(int i, int j) {
//     return i + j;
// }

PYBIND11_MODULE(_rosextpy_pybind11, m) {
    m.doc() = R"pbdoc(
        Python library for rosext(ros2) library
        -----------------------

        .. currentmodule:: rosextpy

        .. autosummary::
           :toctree: _generate

           create_ros_message_serialized_msg
           convert_from_py_serialized_msg
           convert_to_py_serialized_msg
           destroy_ros_message_serialized_msg
           get_type_support
    )pbdoc";

    // py::class_ <rosextpy::Node>(m,"Node", py::dynamic_attr())
    //     .def(py::init<const std::string &>())
    //     .def(py::init<const std::string &,const std::string &>())
    //     .def("getName", &rosextpy::Node::getName, py::return_value_policy::reference)
    //     .def("create_generic_subscription", &rosextpy::Node::create_generic_subscription);

    // m.def("init", &rosextpy::init);
    // m.def("add", &add, "A function which adds two numbers");
    m.def("create_ros_message_serialized_msg", &rosextpy::create_ros_message_serialized_msg);
    m.def("convert_from_py_serialized_msg", &rosextpy::convert_from_py_serialized_msg);
    m.def("convert_to_py_serialized_msg", &rosextpy::convert_to_py_serialized_msg);
    m.def("destroy_ros_message_serialized_msg", &rosextpy::destroy_ros_message_serialized_msg);
    m.def("get_type_support", &rosextpy::get_type_support);

#ifdef VERSION_INFO
    m.attr("__version__") = MACRO_STRINGIFY(VERSION_INFO);
#else
    m.attr("__version__") = "dev";
#endif
}
