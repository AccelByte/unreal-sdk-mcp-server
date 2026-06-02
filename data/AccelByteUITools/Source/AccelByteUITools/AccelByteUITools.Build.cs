using UnrealBuildTool;

public class AccelByteUITools : ModuleRules
{
	public AccelByteUITools(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"UMG",
			"CommonUI",
			"SlateCore"
		});
	}
}
