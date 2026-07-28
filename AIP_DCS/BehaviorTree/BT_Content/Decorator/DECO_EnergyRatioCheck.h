#pragma once
#include "../../behaviortree_cpp_v3/action_node.h"
#include "../../behaviortree_cpp_v3/bt_factory.h"
#include "../../../Geometry/Vector3.h"
#include <iostream>
#include "../Functions.h"
#include "../BlackBoard/CPPBlackBoard.h"

using namespace BT;

namespace Action
{
	class DECO_EnergyRatioCheck : public SyncActionNode
	{
	private:


	public:


		DECO_EnergyRatioCheck(const std::string& name, const NodeConfiguration& config) : SyncActionNode(name, config)
		{
		}

		~DECO_EnergyRatioCheck()
		{

		}

		static PortsList providedPorts();

		NodeStatus tick() override;
	};
}
