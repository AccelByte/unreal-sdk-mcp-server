using UnrealBuildTool;

public class WidgetBlueprintGeneratorEditor : ModuleRules
{
	public WidgetBlueprintGeneratorEditor(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"AssetTools",
			"Blutility",
			"EditorScriptingUtilities",
			"Json",
			"JsonUtilities",
			"UMG",
			"UMGEditor",
			"UnrealEd"
		});

		PrivateDependencyModuleNames.AddRange(new string[]
		{
			"Projects"
		});
	}
}
