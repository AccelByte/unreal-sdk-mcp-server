// Copyright (c) 2026 AccelByte Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "AccelByteUIToolsLibrary.generated.h"

UCLASS()
class ACCELBYTEUITOOLSEDITOR_API UAccelByteUIToolsLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "AccelByte UI Tools|Editor")
	static bool CreateWidgetBlueprint(const FString& AssetPath, const FString& ParentClassPath, const bool bForce, FString& OutError);

	UFUNCTION(BlueprintCallable, Category = "AccelByte UI Tools|Editor")
	static bool PopulateWidgetBlueprintFromJson(const FString& AssetPath, const FString& SpecJson, FString& OutError);

	UFUNCTION(BlueprintCallable, Category = "AccelByte UI Tools|Editor")
	static bool AddWidgetToWidgetBlueprintFromJson(const FString& AssetPath, const FString& ParentWidgetName, const FString& WidgetJson, FString& OutError);

	UFUNCTION(BlueprintCallable, Category = "AccelByte UI Tools|Editor")
	static bool UpdateWidgetPropertiesInWidgetBlueprintFromJson(const FString& AssetPath, const FString& WidgetName, const FString& PropertiesJson, FString& OutError);

	UFUNCTION(BlueprintCallable, Category = "AccelByte UI Tools|Editor")
	static int32 ReadWidgetBlueprintHierarchy(const FString& AssetPath, TArray<FString>& OutWidgetNames, FString& OutError);

	UFUNCTION(BlueprintCallable, Category = "AccelByte UI Tools|Editor")
	static bool VerifyWidgetBlueprintCollectionEntries(const FString& AssetPath, const FString& SpecJson, TArray<FString>& OutCollectionEntryAssignments, FString& OutError);

	UFUNCTION(BlueprintCallable, Category = "AccelByte UI Tools|Editor")
	static bool VerifyExpectedWidgetClassesStable(const FString& SpecJson, TArray<FString>& OutWidgetClassAssignments, FString& OutError);

	UFUNCTION(BlueprintCallable, Category = "AccelByte UI Tools|Editor")
	static bool VerifyParentWidgetBindings(const FString& ParentClassPath, const FString& SpecJson, TArray<FString>& OutBindingAssignments, FString& OutError);

	UFUNCTION(BlueprintCallable, Category = "AccelByte UI Tools|Editor")
	static bool VerifyWidgetBlueprintClasses(const FString& AssetPath, const FString& SpecJson, TArray<FString>& OutWidgetClassAssignments, FString& OutError);
};
