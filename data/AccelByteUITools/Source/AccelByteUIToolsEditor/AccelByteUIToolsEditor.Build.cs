using UnrealBuildTool;

public class AccelByteUIToolsEditor : ModuleRules
{
	public AccelByteUIToolsEditor(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		bUseUnity = false;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"HTTPServer",
			"AccelByteUITools"
		});

		PrivateDependencyModuleNames.AddRange(new string[]
		{
			"AssetTools",
			"Blutility",
			"CommonUI",
			"EditorScriptingUtilities",
			"Engine",
			"Json",
			"Kismet",
			"Slate",
			"SlateCore",
			"LiveCoding",
			"UMG",
			"UMGEditor",
			"UnrealEd"
		});
	}
}

