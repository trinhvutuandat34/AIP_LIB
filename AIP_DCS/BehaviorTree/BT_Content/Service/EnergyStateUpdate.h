#pragma once
#include "../../behaviortree_cpp_v3/action_node.h"
#include "../../behaviortree_cpp_v3/bt_factory.h"
#include "../../../Geometry/Vector3.h"
#include "../../../Geometry/Quaternion.h"
#include "../Functions.h"
#include "../BlackBoard/CPPBlackBoard.h"

using namespace BT;

namespace Action
{
	class EnergyStateUpdate : public SyncActionNode
	{
	private:


	public:


		EnergyStateUpdate(const std::string& name, const NodeConfiguration& config) : SyncActionNode(name, config)
		{
		}

		~EnergyStateUpdate()
		{

		}

		static PortsList providedPorts();

		NodeStatus tick() override;
	};
}
