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

// rosext.create_generic_pubsub (rosext)
// Author: paraby@gmail.com

#ifndef ROSEXT__CREATE_GENERIC_PUBSUB_HPP_
#define ROSEXT__CREATE_GENERIC_PUBSUB_HPP_
#include <string>
#include "rclcpp/node.hpp"
#include "generic_subscription.hpp"
#include "generic_publisher.hpp"

namespace rosext
{
template<typename AllocatorT = std::allocator<void>>
std::shared_ptr<GenericPublisher> create_generic_publisher(
  rclcpp::node_interfaces::NodeTopicsInterface::SharedPtr topics_interface,
  const std::string & topic_name,
  const std::string & topic_type,
  const rclcpp::QoS & qos,
  const rclcpp::PublisherOptionsWithAllocator<AllocatorT> & options = (
    rclcpp::PublisherOptionsWithAllocator<AllocatorT>()
  )
)
{
  auto pub = std::make_shared<GenericPublisher>(
    topics_interface->get_node_base_interface(),
    topic_name,
    topic_type,
    qos,
    options);
  topics_interface->add_publisher(pub, options.callback_group);
  return pub;
}


template<typename AllocatorT = std::allocator<void>>
std::shared_ptr<GenericSubscription> create_generic_subscription(
  rclcpp::node_interfaces::NodeTopicsInterface::SharedPtr topics_interface,
  const std::string & topic_name,
  const std::string & topic_type,
  const rclcpp::QoS & qos,
  std::function<void(std::shared_ptr<rclcpp::SerializedMessage>)> callback,
  const rclcpp::SubscriptionOptionsWithAllocator<AllocatorT> & options = (
    rclcpp::SubscriptionOptionsWithAllocator<AllocatorT>()
  )
)
{
  auto subscription = std::make_shared<GenericSubscription>(
    topics_interface->get_node_base_interface(),
    topic_name,
    topic_type,
    qos,
    callback,
    options);

  topics_interface->add_subscription(subscription, options.callback_group) ;
  return subscription;
}

} // namespace rosext
#endif //ROSEXT__CREATE_GENERIC_PUBSUB_HPP_