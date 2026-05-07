// Copyright (c) 2026 AccelByte Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "WidgetBlueprintGeneratorLibrary.generated.h"

UCLASS()
class WIDGETBLUEPRINTGENERATOREDITOR_API UWidgetBlueprintGeneratorLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "Widget Blueprint Generator|Editor")
	static bool CreateWidgetBlueprint(const FString& AssetPath, const FString& ParentClassPath, const bool bForce, FString& OutError);

	UFUNCTION(BlueprintCallable, Category = "Widget Blueprint Generator|Editor")
	static bool PopulateWidgetBlueprintFromJson(const FString& AssetPath, const FString& SpecJson, FString& OutError);

	UFUNCTION(BlueprintCallable, Category = "Widget Blueprint Generator|Editor")
	static bool AddWidgetToWidgetBlueprintFromJson(const FString& AssetPath, const FString& ParentWidgetName, const FString& WidgetJson, FString& OutError);

	UFUNCTION(BlueprintCallable, Category = "Widget Blueprint Generator|Editor")
	static int32 ReadWidgetBlueprintHierarchy(const FString& AssetPath, TArray<FString>& OutWidgetNames, FString& OutError);
};
