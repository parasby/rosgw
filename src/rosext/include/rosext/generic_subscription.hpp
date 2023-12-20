// Copyright 2018, Bosch Software Innovations GmbH.
// Copyright 2021, Apex.AI Inc.
// Copyright 2021, ETRI.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

// rosext.generic_subscription (rosext)
// modified by: paraby@gmail.com

#ifndef ROSEXT__GENERIC_SUBSCRIPTION_HPP_
#define ROSEXT__GENERIC_SUBSCRIPTION_HPP_

#include <functional>
#include <memory>
#include <string>

#include "rcpputils/shared_library.hpp"

#include "rclcpp/callback_group.hpp"
#include "rclcpp/macros.hpp"
#include "rclcpp/node_interfaces/node_base_interface.hpp"
#include "rclcpp/node_interfaces/node_topics_interface.hpp"
#include "rclcpp/qos.hpp"
#include "rclcpp/serialized_message.hpp"
#include "rclcpp/subscription_base.hpp"
#include "rclcpp/visibility_control.hpp"

#include "generic_type_support.hpp"

using namespace rclcpp;

namespace rosext
{

/// %Subscription for serialized messages whose type is not known at running system.
/**
 * Since the type is not known at running system, 
 * this can be used only to forward or log the serialized message.*
 * 
 */
class GenericSubscription : public rclcpp::SubscriptionBase
{
public:
  // cppcheck-suppress unknownMacro
  RCLCPP_SMART_PTR_DEFINITIONS(GenericSubscription)

  /// Constructor.
  /**
   * In order to properly subscribe to a topic, this subscription needs to be added to
   * the node_topic_interface of the node passed into this constructor.
   *
   * \sa rosext::ExtNode::create_generic_subscription() or rosext::create_generic_subscription() for
   * creating an instance of this class and adding it to the node_topic_interface.
   *
   * \param node_base Pointer to parent node's NodeBaseInterface
   * \param ts_lib Type support library, needs to correspond to topic_type
   * \param topic_name Topic name
   * \param topic_type Topic type
   * \param qos %QoS settings
   * \param callback Callback for new messages of serialized form
   * \param options %Subscription options.
   * Not all subscription options are currently respected, the only relevant options for this
   * subscription are `event_callbacks`, `use_default_callbacks`, `ignore_local_publications`, and
   * `%callback_group`.
   */
  template<typename AllocatorT = std::allocator<void>>
  GenericSubscription(
    rclcpp::node_interfaces::NodeBaseInterface * node_base,
    // const std::shared_ptr<rcpputils::SharedLibrary> ts_lib,
    const std::string & topic_name,
    const std::string & topic_type,
    const rclcpp::QoS & qos,
    // TODO(nnmm): Add variant for callback with message info. See issue #1604.
    std::function<void(std::shared_ptr<rclcpp::SerializedMessage>)> callback,
    const rclcpp::SubscriptionOptionsWithAllocator<AllocatorT> & options)
  : SubscriptionBase(
      node_base,      
      *get_generic_typesupport_handle(topic_type, "rosidl_typesupport_cpp"),
      topic_name,
      options.template to_rcl_subscription_options<rclcpp::SerializedMessage>(qos),
      true),
    callback_(callback)       
  {    
    if (options.event_callbacks.deadline_callback) {
      this->add_event_handler(
        options.event_callbacks.deadline_callback,
        RCL_SUBSCRIPTION_REQUESTED_DEADLINE_MISSED);
    }
    if (options.event_callbacks.liveliness_callback) {
      this->add_event_handler(
        options.event_callbacks.liveliness_callback,
        RCL_SUBSCRIPTION_LIVELINESS_CHANGED);
    }
    if (options.event_callbacks.incompatible_qos_callback) {
      this->add_event_handler(
        options.event_callbacks.incompatible_qos_callback,
        RCL_SUBSCRIPTION_REQUESTED_INCOMPATIBLE_QOS);
    } else if (options.use_default_callbacks) {
      // Register default callback when not specified
      try {
        this->add_event_handler(
          [this](QOSRequestedIncompatibleQoSInfo & info) {
            this->default_incompatible_qos_callback(info);
          },
          RCL_SUBSCRIPTION_REQUESTED_INCOMPATIBLE_QOS);
      } catch (UnsupportedEventTypeException & /*exc*/) {
        // pass
      }
    }

    /*if (options.event_callbacks.message_lost_callback) {
      this->add_event_handler(
        options.event_callbacks.message_lost_callback,
        RCL_SUBSCRIPTION_MESSAGE_LOST);
    }*/
  }

  RCLCPP_PUBLIC
  virtual ~GenericSubscription() = default;

  // Same as create_serialized_message() as the subscription is to serialized_messages only
  RCLCPP_PUBLIC
  std::shared_ptr<void> create_message() override;

  RCLCPP_PUBLIC
  std::shared_ptr<rclcpp::SerializedMessage> create_serialized_message() override;

  /// Cast the message to a rclcpp::SerializedMessage and call the callback.
  RCLCPP_PUBLIC
  void handle_message(
    std::shared_ptr<void> & message, const rclcpp::MessageInfo & message_info) override;

  /// This function is currently not implemented.
  RCLCPP_PUBLIC
  void handle_loaned_message(
    void * loaned_message, const rclcpp::MessageInfo & message_info) override;

  // Same as return_serialized_message() as the subscription is to serialized_messages only
  RCLCPP_PUBLIC
  void return_message(std::shared_ptr<void> & message) override;

  RCLCPP_PUBLIC
  void return_serialized_message(std::shared_ptr<rclcpp::SerializedMessage> & message) override;

private:
  RCLCPP_DISABLE_COPY(GenericSubscription)

  std::function<void(std::shared_ptr<rclcpp::SerializedMessage>)> callback_;
};

}  // namespace rclcpp

#endif  // ROSEXT__GENERIC_SUBSCRIPTION_HPP_
