// Copyright (c) 2026 AccelByte Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Commandlets/Commandlet.h"
#include "AccelByteUIToolsCommandlet.generated.h"

UCLASS()
class ACCELBYTEUITOOLSEDITOR_API UAccelByteUIToolsCommandlet : public UCommandlet
{
	GENERATED_BODY()

public:
	UAccelByteUIToolsCommandlet();

	virtual int32 Main(const FString& Params) override;
};
