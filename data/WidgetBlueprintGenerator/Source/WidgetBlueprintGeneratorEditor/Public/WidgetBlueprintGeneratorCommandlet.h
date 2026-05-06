// Copyright (c) 2026 AccelByte Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Commandlets/Commandlet.h"
#include "WidgetBlueprintGeneratorCommandlet.generated.h"

UCLASS()
class WIDGETBLUEPRINTGENERATOREDITOR_API UWidgetBlueprintGeneratorCommandlet : public UCommandlet
{
	GENERATED_BODY()

public:
	UWidgetBlueprintGeneratorCommandlet();

	virtual int32 Main(const FString& Params) override;
};
