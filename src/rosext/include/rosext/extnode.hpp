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

// rosext.extnode (rosext)
// Author: paraby@gmail.com

#ifndef ROSEXT__EXTNODE_HPP_
#define ROSEXT__EXTNODE_HPP_
#include "rclcpp/node.hpp"
#include "generic_subscription.hpp"
#include "generic_publisher.hpp"

namespace rosext
{
  /// %Special Purpose Node to subscribe or publish for serialized messages whose type is not known at the running system.
/** 
 * 
 */
  class ExtNode : public rclcpp::Node
  {
  public:
    explicit ExtNode(
        const std::string &node_name);

    explicit ExtNode(
        const std::string &node_name,
        const std::string &namespace_);

    template <typename AllocatorT = std::allocator<void>>
    std::shared_ptr<rosext::GenericPublisher> create_generic_publisher(
        const std::string &topic_name,
        const std::string &topic_type,
        const rclcpp::QoS &qos,
        const rclcpp::PublisherOptionsWithAllocator<AllocatorT> &options = (
          rclcpp::PublisherOptionsWithAllocator<AllocatorT>()));

    template <typename AllocatorT = std::allocator<void>>
    std::shared_ptr<rosext::GenericSubscription> create_generic_subscription(
        const std::string &topic_name,
        const std::string &topic_type,
        const rclcpp::QoS &qos,
        std::function<void(std::shared_ptr<rclcpp::SerializedMessage>)> callback,
        const rclcpp::SubscriptionOptionsWithAllocator<AllocatorT> &options = (
          rclcpp::SubscriptionOptionsWithAllocator<AllocatorT>()));

    virtual ~ExtNode();
  };
} // namespace rosext

#ifndef ROSEXT__EXTNODE_IMPL_HPP_
// Template implementations
#include "extnode_impl.hpp"
#endif

#endif // ROSEXT__EXTNODE_HPP_
